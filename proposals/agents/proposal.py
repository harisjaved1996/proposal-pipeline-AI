"""
Proposal Agent — reads client_matrix.json, calls OpenRouter, returns a validated ProposalDocument.

Yields (event_type, payload_dict) tuples so the SSE view can stream progress.
"""
from __future__ import annotations

import json
import os
import time
from typing import Generator, Tuple

from decouple import config
from openai import OpenAI
from pydantic import ValidationError

from ..schemas import ProposalDocument

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL = "openrouter/auto"

SYSTEM_PROMPT = """You are a senior consulting proposal writer. You will be given a structured client analysis matrix (JSON) and must produce a complete consulting engagement proposal.

RESPOND WITH VALID JSON ONLY — no markdown, no text outside the JSON object.

─────────────────────────────────────────────────────────
REQUIRED JSON SHAPE
─────────────────────────────────────────────────────────
{
  "executive_summary": { "title": "Executive Summary", "body": "...", "bullets": [] },
  "understanding":     { "title": "Understanding of Client Needs", "body": "...", "bullets": ["..."] },
  "approach":          { "title": "Proposed Approach", "body": "...", "bullets": ["..."] },
  "phases_timeline": [
    {
      "phase_number": 1,
      "phase_name": "...",
      "duration": "...",
      "deliverables": ["..."],
      "description": "..."
    }
  ],
  "pricing_approach": { "title": "Pricing Approach", "body": "...", "bullets": [] },
  "open_questions": [
    {
      "question": "...",
      "source_statement": "...",
      "confidence": "low" | "contradicted",
      "dimension": "business" | "technical" | "operational" | "strategic"
    }
  ],
  "client_name": "...",
  "total_duration_estimate": "...",
  "engagement_type": "..."
}

─────────────────────────────────────────────────────────
SECTION GUIDANCE
─────────────────────────────────────────────────────────
executive_summary:  2–3 paragraphs. Summarise the client's situation, what they need, and what the engagement will deliver.

understanding:  Draw directly from business/operational/strategic pain_points and desired_state cells. Use bullets to highlight top 4–6 needs.

approach:  Describe the consulting methodology and why it fits. Reference technical dimension items. 3–5 methodology bullets.

phases_timeline:  3–5 phases with concrete deliverables. Duration must be specific (e.g. "2 weeks", "4–6 weeks").

pricing_approach:  Describe the pricing model and what drives variation. Be transparent about assumptions.

open_questions:  ONLY include items from the matrix where confidence = "low" OR confidence = "contradicted". Phrase each as a direct question to the client. If no low/contradicted items exist, return an empty array.

─────────────────────────────────────────────────────────
RULES
─────────────────────────────────────────────────────────
• Write in professional consulting tone — clear, confident, client-facing
• body fields are plain text paragraphs (NO markdown symbols)
• bullets fields are short phrases, not full sentences
• Never fabricate facts not derivable from the matrix
• Do NOT wrap the JSON in markdown code fences
"""


# ── Retry on schema validation failure ───────────────────────────────────────

def _repair_proposal(client: OpenAI, bad_json: str, error_msg: str) -> ProposalDocument:
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
    return ProposalDocument.model_validate_json(resp.choices[0].message.content)


# ── Main generator ────────────────────────────────────────────────────────────

Event = Tuple[str, dict]


def run_proposal(proposal) -> Generator[Event, None, None]:  # noqa: ANN001
    """
    Generator — yields (event_type, payload) for each pipeline step.
    Event types: step | info | success | warning | error | complete
    """

    yield ("step", {"message": "Initialising Proposal Agent", "icon": "file-contract"})

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config("OPENROUTER_API_KEY"),
    )

    # ── 1. Load client matrix ─────────────────────────────────────────────────
    yield ("step", {"message": "Loading client matrix from debrief output", "icon": "database"})

    matrix_path = os.path.join("runs", str(proposal.run_id), "client_matrix.json")
    if not os.path.exists(matrix_path):
        yield ("error", {"message": f"client_matrix.json not found at {matrix_path} — run the Debrief Agent first."})
        raise RuntimeError(f"client_matrix.json not found: {matrix_path}")

    with open(matrix_path, "r", encoding="utf-8") as fh:
        matrix_dict = json.load(fh)

    yield ("success", {"message": f"Loaded matrix  →  {matrix_path}"})

    # ── 2. Scan for low/contradicted items ────────────────────────────────────
    yield ("step", {"message": "Scanning matrix for low-confidence and contradicted items", "icon": "search"})

    dims = ["business", "technical", "operational", "strategic"]
    cols = ["pain_points", "desired_state", "success_criteria", "risks_unknowns"]
    flagged: list[dict] = []

    for dim in dims:
        for col in cols:
            for item in matrix_dict.get(dim, {}).get(col, []):
                if item.get("confidence") in ("low", "contradicted"):
                    flagged.append({**item, "dimension": dim, "column": col})

    if flagged:
        yield ("info", {"message": f"Found {len(flagged)} item(s) with low/contradicted confidence → will surface as Open Questions"})
    else:
        yield ("info", {"message": "All matrix items have high or medium confidence — no Open Questions expected"})

    # ── 3. Build prompt ───────────────────────────────────────────────────────
    yield ("step", {"message": "Building proposal prompt", "icon": "pencil-alt"})

    matrix_json = json.dumps(matrix_dict, indent=2)
    user_prompt = (
        "Analyse the following client matrix and write a complete consulting proposal.\n\n"
        f"CLIENT MATRIX:\n{matrix_json}\n\n"
        "Generate the ProposalDocument JSON now."
    )
    prompt_chars = len(SYSTEM_PROMPT) + len(user_prompt)
    yield ("info", {"message": f"Prompt assembled  ({prompt_chars:,} characters)"})

    # ── 4. Call OpenRouter ────────────────────────────────────────────────────
    yield ("step", {"message": f"Calling AI model  [{MODEL}]", "icon": "brain"})
    yield ("info", {"message": "Generating proposal document … this may take 30 – 120 seconds."})

    t0 = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    latency_ms = int((time.time() - t0) * 1000)

    tokens_in  = response.usage.prompt_tokens if response.usage else "?"
    tokens_out = response.usage.completion_tokens if response.usage else "?"
    yield ("success", {
        "message": (
            f"Model responded in {latency_ms:,} ms"
            f"  ·  {tokens_in} prompt tokens  /  {tokens_out} completion tokens"
        )
    })

    raw_json = response.choices[0].message.content

    # ── Stream raw output ─────────────────────────────────────────────────────
    yield ("raw_output", {"message": "Raw model output received", "raw": raw_json})

    # ── 5. Validate schema ────────────────────────────────────────────────────
    yield ("step", {"message": "Validating proposal structure", "icon": "check-square"})

    try:
        proposal_doc = ProposalDocument.model_validate_json(raw_json)
        yield ("success", {"message": "Schema validation passed on first attempt"})
    except ValidationError as exc:
        yield ("warning", {"message": f"Schema mismatch ({exc.error_count()} field(s)) — attempting auto-repair …"})
        try:
            proposal_doc = _repair_proposal(client, raw_json, str(exc))
            yield ("success", {"message": "Schema validation passed after repair"})
        except Exception as exc2:
            yield ("error", {"message": f"Could not recover from validation error: {exc2}"})
            raise RuntimeError(str(exc2)) from exc2

    # ── 6. Save JSON ──────────────────────────────────────────────────────────
    yield ("step", {"message": "Saving proposal JSON", "icon": "save"})

    proposal.output_json = proposal_doc.model_dump_json()
    proposal.raw_output  = raw_json
    proposal.save(update_fields=["output_json", "raw_output"])
    yield ("success", {"message": "Proposal JSON saved to database"})

    # ── 7. Generate docx ──────────────────────────────────────────────────────
    yield ("step", {"message": "Generating Word document (.docx)", "icon": "file-word"})

    from ..utils.docx_builder import build_proposal_docx

    output_dir = os.path.join("runs", str(proposal.run_id))
    os.makedirs(output_dir, exist_ok=True)
    docx_path = os.path.join(output_dir, "proposal.docx")

    build_proposal_docx(proposal_doc, docx_path)

    proposal.docx_path = docx_path
    proposal.save(update_fields=["docx_path"])
    yield ("success", {"message": f"Word document saved  →  {docx_path}"})

    # ── 8. Stats ──────────────────────────────────────────────────────────────
    phase_count = len(proposal_doc.phases_timeline)
    oq_count    = len(proposal_doc.open_questions)
    yield ("info", {
        "message": (
            f"6 sections  ·  {phase_count} phase(s)  ·  {oq_count} open question(s)"
        )
    })

    if oq_count:
        yield ("warning", {
            "message": f"{oq_count} open question(s) flagged from low/contradicted confidence items"
        })

    # ── 9. Done ───────────────────────────────────────────────────────────────
    yield ("complete", {
        "message": "Proposal Agent finished successfully!",
        "proposal": proposal_doc.model_dump(),
        "raw_output": raw_json,
    })
