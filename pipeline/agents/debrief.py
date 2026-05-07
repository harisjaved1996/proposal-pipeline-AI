"""
Debrief Agent — reads intake files, calls OpenRouter, returns a validated ClientMatrix.

Yields (event_type, payload_dict) tuples so the SSE view can stream progress.
"""
from __future__ import annotations

import json
import os
import time
from typing import Generator, Tuple

import fitz  # PyMuPDF
from decouple import config
from openai import OpenAI
from pydantic import ValidationError

from ..schemas import ClientMatrix, MatrixRow

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL = "openrouter/auto"

SYSTEM_PROMPT = """You are an expert consulting analyst. Analyse the client documents provided and extract two things:

1. A 4×4 client matrix (business / technical / operational / strategic dimensions).
2. A complete stakeholder registry — every named person mentioned in the documents.

RESPOND WITH VALID JSON ONLY — no markdown, no text outside the JSON object.

─────────────────────────────────────────────────────────
REQUIRED JSON SHAPE
─────────────────────────────────────────────────────────
{
  "business":    { "pain_points": [...], "desired_state": [...], "success_criteria": [...], "risks_unknowns": [...] },
  "technical":   { "pain_points": [...], "desired_state": [...], "success_criteria": [...], "risks_unknowns": [...] },
  "operational": { "pain_points": [...], "desired_state": [...], "success_criteria": [...], "risks_unknowns": [...] },
  "strategic":   { "pain_points": [...], "desired_state": [...], "success_criteria": [...], "risks_unknowns": [...] },
  "stakeholders": [...]
}

─────────────────────────────────────────────────────────
MATRIX ITEM SCHEMA (used in all 16 cells above)
─────────────────────────────────────────────────────────
{
  "statement":          "clear, specific insight extracted from the documents",
  "confidence":         "high" | "medium" | "low" | "contradicted",
  "source_excerpt":     "exact verbatim quote from the document",
  "contradiction_note": "explanation of the conflict"  ← REQUIRED only when confidence = "contradicted"
}

Confidence guide:
  high         — explicitly and clearly stated
  medium       — reasonably implied
  low          — uncertain, vague, or poorly supported
  contradicted — the documents contain conflicting information on this point

Matrix rules:
  • 2–5 items per cell
  • source_excerpt must be a direct quote from the provided text
  • Never fabricate facts not present in the documents
  • contradiction_note is REQUIRED when confidence = "contradicted"

─────────────────────────────────────────────────────────
STAKEHOLDER SCHEMA (one entry per named person)
─────────────────────────────────────────────────────────
{
  "name":              "Full name or best available name from documents",
  "title":             "Job title or role as stated",
  "role_in_decision":  "Their specific role in the buying/approval process (e.g. budget approver, technical sign-off, end user, champion, gatekeeper)",
  "stance":            "champion" | "neutral" | "skeptic" | "unknown",
  "influence":         "high" | "medium" | "low",
  "key_concern":       "Their single most important concern or priority based on the documents",
  "source_excerpt":    "Exact quote from the document that best characterises this person"
}

Stance guide:
  champion  — actively supportive of the engagement / change
  skeptic   — resistant, cautious, or has raised objections
  neutral   — not clearly for or against
  unknown   — insufficient information to determine stance

Stakeholder rules:
  • Include EVERY named individual mentioned in the documents — do not skip anyone
  • If a person is mentioned only briefly, still include them with influence = "low" and stance = "unknown"
  • Do NOT include unnamed groups (e.g. "drivers", "dispatchers") — named individuals only
  • Do NOT wrap the JSON in markdown code fences
"""


# ── File reading ──────────────────────────────────────────────────────────────

def _extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext in (".pdf", ".docx", ".doc"):
        try:
            doc = fitz.open(path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text or f"[{os.path.basename(path)}: file opened but no text extracted]"
        except Exception as exc:
            return f"[Could not read {os.path.basename(path)}: {exc}]"

    if ext == ".md":
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except Exception as exc:
            return f"[Could not read {os.path.basename(path)}: {exc}]"

    return f"[Unsupported format: {ext}]"


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_prompt(documents: list[dict]) -> str:
    sections = "\n\n---\n\n".join(
        f"### FILE: {os.path.basename(d['path'])}\n\n{d['text']}"
        for d in documents
    )
    return (
        "Analyse the following client documents and return the 4×4 client matrix JSON.\n\n"
        + sections
    )


# ── Retry on schema validation failure ───────────────────────────────────────

def _repair_matrix(client: OpenAI, bad_json: str, error_msg: str) -> ClientMatrix:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": bad_json},
            {
                "role": "user",
                "content": (
                    f"The JSON has schema validation errors:\n{error_msg}\n\n"
                    "Fix all errors and return the corrected JSON object only."
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return ClientMatrix.model_validate_json(resp.choices[0].message.content)


# ── Main generator ────────────────────────────────────────────────────────────

Event = Tuple[str, dict]


def run_debrief(run) -> Generator[Event, None, None]:  # noqa: ANN001
    """
    Generator — yields (event_type, payload) for each pipeline step.
    Event types: step | info | success | warning | error | complete
    """

    yield ("step", {"message": "Initialising Debrief Agent", "icon": "robot"})

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config("OPENROUTER_API_KEY"),
    )

    # ── 1. Read files ─────────────────────────────────────────────────────────
    yield ("step", {"message": f"Reading {len(run.file_paths)} uploaded document(s)", "icon": "folder-open"})

    documents: list[dict] = []
    for path in run.file_paths:
        yield ("info", {"message": f"Extracting text from  {os.path.basename(path)} …"})
        text = _extract_text(path)
        char_count = len(text)
        documents.append({"path": path, "text": text})
        yield ("success", {"message": f"{os.path.basename(path)}  —  {char_count:,} characters"})

    total_chars = sum(len(d["text"]) for d in documents)
    yield ("info", {"message": f"Total content: {total_chars:,} characters across {len(documents)} file(s)"})

    # ── 2. Build prompt ───────────────────────────────────────────────────────
    yield ("step", {"message": "Building analysis prompt", "icon": "pencil-alt"})
    user_prompt = _build_user_prompt(documents)
    prompt_chars = len(SYSTEM_PROMPT) + len(user_prompt)
    yield ("info", {"message": f"Prompt assembled  ({prompt_chars:,} characters)"})

    # ── 3. Call OpenRouter ────────────────────────────────────────────────────
    yield ("step", {"message": f"Calling AI model  [{MODEL}]", "icon": "brain"})
    yield ("info", {"message": "Sending documents to the language model for analysis …"})
    yield ("info", {"message": "This may take 20 – 90 seconds depending on document size."})

    t0 = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    latency_ms = int((time.time() - t0) * 1000)

    tokens_in = response.usage.prompt_tokens if response.usage else "?"
    tokens_out = response.usage.completion_tokens if response.usage else "?"
    yield ("success", {
        "message": (
            f"Model responded in {latency_ms:,} ms"
            f"  ·  {tokens_in} prompt tokens  /  {tokens_out} completion tokens"
        )
    })

    raw_json = response.choices[0].message.content

    # ── Stream raw model output to user ───────────────────────────────────────
    yield ("raw_output", {"message": "Raw model output received", "raw": raw_json})

    # ── 4. Validate schema ────────────────────────────────────────────────────
    yield ("step", {"message": "Validating and structuring client matrix", "icon": "table"})

    try:
        matrix = ClientMatrix.model_validate_json(raw_json)
        yield ("success", {"message": "Schema validation passed on first attempt"})
    except ValidationError as exc:
        yield ("warning", {"message": f"Schema mismatch ({exc.error_count()} field(s)) — attempting auto-repair …"})
        try:
            matrix = _repair_matrix(client, raw_json, str(exc))
            yield ("success", {"message": "Schema validation passed after repair"})
        except Exception as exc2:
            yield ("error", {"message": f"Could not recover from validation error: {exc2}"})
            raise RuntimeError(str(exc2)) from exc2

    # ── 5. Stats ──────────────────────────────────────────────────────────────
    dims = ["business", "technical", "operational", "strategic"]
    cols = ["pain_points", "desired_state", "success_criteria", "risks_unknowns"]

    all_items = [
        item
        for dim in dims
        for col in cols
        for item in getattr(getattr(matrix, dim), col)
    ]
    contradicted = [i for i in all_items if i.confidence == "contradicted"]
    low_conf = [i for i in all_items if i.confidence == "low"]

    yield ("info", {"message": f"Extracted {len(all_items)} items across the 4 × 4 matrix"})

    stakeholders = matrix.stakeholders
    if stakeholders:
        champions = [s for s in stakeholders if s.stance == "champion"]
        skeptics  = [s for s in stakeholders if s.stance == "skeptic"]
        yield ("success", {
            "message": (
                f"Identified {len(stakeholders)} stakeholder(s): "
                f"{len(champions)} champion(s), {len(skeptics)} skeptic(s)"
            )
        })
        for s in stakeholders:
            yield ("info", {"message": f"  · {s.name} [{s.title}] — {s.stance} / influence: {s.influence}"})
    else:
        yield ("warning", {"message": "No named stakeholders found in the documents"})

    if contradicted:
        yield ("warning", {
            "message": f"{len(contradicted)} contradicted item(s) flagged — will surface in Open Questions"
        })
    if low_conf:
        yield ("info", {"message": f"{len(low_conf)} low-confidence item(s) noted"})

    # ── 6. Save output ────────────────────────────────────────────────────────
    yield ("step", {"message": "Saving results to disk", "icon": "save"})

    output_dir = os.path.join("runs", str(run.id))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "client_matrix.json")

    matrix_dict = matrix.model_dump()
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(matrix_dict, fh, indent=2)

    run.output_path = output_path
    run.output_json = matrix.model_dump_json()
    run.raw_output = raw_json
    run.save(update_fields=["output_path", "output_json", "raw_output"])

    yield ("success", {"message": f"Saved  →  {output_path}"})

    # ── 7. Done ───────────────────────────────────────────────────────────────
    yield ("complete", {
        "message": "Debrief Agent finished successfully!",
        "matrix": matrix_dict,
        "raw_output": raw_json,
    })
