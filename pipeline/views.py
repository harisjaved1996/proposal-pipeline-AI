from __future__ import annotations

import json
import os
import uuid

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import RunRecord

ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx", ".md"]

_DIMENSIONS = [
    ("business",    "Business",    "business",    "fa-briefcase"),
    ("technical",   "Technical",   "technical",   "fa-cogs"),
    ("operational", "Operational", "operational", "fa-tasks"),
    ("strategic",   "Strategic",   "strategic",   "fa-chess"),
]


# ── Upload page ───────────────────────────────────────────────────────────────

def upload_intake(request: HttpRequest) -> HttpResponse:
    errors: list[str] = []

    if request.method == "POST":
        files = request.FILES.getlist("files")

        if not files:
            errors.append("No files received — please select at least one document.")
        else:
            for f in files:
                name = f.name.lower()
                if not any(name.endswith(ext) for ext in ACCEPTED_EXTENSIONS):
                    errors.append(
                        f'"{f.name}" is not a supported file type. '
                        f'Accepted: {", ".join(ACCEPTED_EXTENSIONS)}'
                    )

        if not errors:
            run = RunRecord.objects.create()

            upload_dir = os.path.join("media", "uploads", str(run.id))
            os.makedirs(upload_dir, exist_ok=True)

            saved_paths: list[str] = []
            for f in files:
                dest = os.path.join(upload_dir, f.name)
                with open(dest, "wb") as fh:
                    for chunk in f.chunks():
                        fh.write(chunk)
                saved_paths.append(dest)

            run.file_paths = saved_paths
            run.save(update_fields=["file_paths"])

            return redirect("pipeline:run_status", run_id=run.id)

    # Ensure CSRF cookie is set even on GET
    get_token(request)
    return render(request, "pipeline/upload.html", {"errors": errors})


# ── Run status page ───────────────────────────────────────────────────────────

def run_status(request: HttpRequest, run_id: uuid.UUID) -> HttpResponse:
    run = get_object_or_404(RunRecord, pk=run_id)
    return render(
        request,
        "pipeline/run_status.html",
        {"run": run, "dimensions": _DIMENSIONS},
    )


# ── SSE stream ────────────────────────────────────────────────────────────────

def run_stream(request: HttpRequest, run_id: uuid.UUID) -> StreamingHttpResponse:
    run = get_object_or_404(RunRecord, pk=run_id)

    def _sse(event_type: str, payload: dict) -> str:
        data = json.dumps({"type": event_type, **payload})
        return f"data: {data}\n\n"

    def event_stream():
        if run.status == RunRecord.Status.COMPLETE:
            yield _sse("cached", {"message": "Results loaded from cache (run already complete)"})
            matrix_data = json.loads(run.output_json)
            raw_output = getattr(run, "raw_output", "")
            yield _sse("complete", {
                "message": "Debrief Agent finished successfully!",
                "matrix": matrix_data,
                "raw_output": raw_output,
            })
            return

        if run.status == RunRecord.Status.FAILED:
            yield _sse("error", {"message": run.error_message or "Run failed."})
            return

        if run.status == RunRecord.Status.RUNNING:
            yield _sse("error", {"message": "This run is already being processed."})
            return

        # PENDING → start
        run.status = RunRecord.Status.RUNNING
        run.save(update_fields=["status"])

        try:
            from .agents.debrief import run_debrief

            for event_type, payload in run_debrief(run):
                yield _sse(event_type, payload)

            run.status = RunRecord.Status.COMPLETE
            run.save(update_fields=["status"])

        except Exception as exc:
            run.status = RunRecord.Status.FAILED
            run.error_message = str(exc)
            run.save(update_fields=["status", "error_message"])
            yield _sse("error", {"message": str(exc)})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
