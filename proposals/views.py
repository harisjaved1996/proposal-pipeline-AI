from __future__ import annotations

import json
import os
import uuid

from django.http import FileResponse, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from pipeline.models import RunRecord

from .models import ProposalRecord


def proposal_stream(request: HttpRequest, run_id: uuid.UUID) -> StreamingHttpResponse:
    run = get_object_or_404(RunRecord, pk=run_id)

    proposal, _ = ProposalRecord.objects.get_or_create(
        run=run,
        defaults={"status": ProposalRecord.Status.PENDING},
    )

    def _sse(event_type: str, payload: dict) -> str:
        data = json.dumps({"type": event_type, **payload})
        return f"data: {data}\n\n"

    def event_stream():
        if proposal.status == ProposalRecord.Status.COMPLETE:
            yield _sse("cached", {"message": "Proposal loaded from cache"})
            proposal_data = json.loads(proposal.output_json)
            yield _sse("complete", {
                "message": "Proposal Agent finished successfully!",
                "proposal": proposal_data,
                "raw_output": proposal.raw_output,
            })
            return

        if proposal.status == ProposalRecord.Status.RUNNING:
            yield _sse("error", {"message": "Proposal generation already in progress."})
            return

        if proposal.status == ProposalRecord.Status.FAILED:
            proposal.status = ProposalRecord.Status.PENDING
            proposal.error_message = ""
            proposal.save(update_fields=["status", "error_message"])

        proposal.status = ProposalRecord.Status.RUNNING
        proposal.save(update_fields=["status"])

        try:
            from .agents.proposal import run_proposal
            for event_type, payload in run_proposal(proposal):
                yield _sse(event_type, payload)
            proposal.status = ProposalRecord.Status.COMPLETE
            proposal.save(update_fields=["status"])
        except Exception as exc:
            proposal.status = ProposalRecord.Status.FAILED
            proposal.error_message = str(exc)
            proposal.save(update_fields=["status", "error_message"])
            yield _sse("error", {"message": str(exc)})

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


def proposal_download_docx(
    request: HttpRequest, run_id: uuid.UUID
) -> FileResponse | HttpResponse:
    run = get_object_or_404(RunRecord, pk=run_id)
    proposal = get_object_or_404(ProposalRecord, run=run)

    if not proposal.docx_path or not os.path.exists(proposal.docx_path):
        return HttpResponse("Document not yet generated.", status=404)

    fh = open(proposal.docx_path, "rb")
    return FileResponse(
        fh,
        as_attachment=True,
        filename=f"proposal_{run_id}.docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


def proposal_status_json(
    request: HttpRequest, run_id: uuid.UUID
) -> HttpResponse:
    run = get_object_or_404(RunRecord, pk=run_id)

    try:
        proposal = ProposalRecord.objects.get(run=run)
        data: dict = {
            "exists": True,
            "status": proposal.status,
            "has_docx": bool(
                proposal.docx_path and os.path.exists(proposal.docx_path)
            ),
        }
        if (
            proposal.status == ProposalRecord.Status.COMPLETE
            and proposal.output_json
        ):
            doc = json.loads(proposal.output_json)
            data["summary"] = {
                "client_name":             doc.get("client_name", ""),
                "total_duration_estimate": doc.get("total_duration_estimate", ""),
                "engagement_type":         doc.get("engagement_type", ""),
                "open_questions_count":    len(doc.get("open_questions", [])),
                "phase_count":             len(doc.get("phases_timeline", [])),
            }
    except ProposalRecord.DoesNotExist:
        data = {"exists": False, "status": None}

    return HttpResponse(json.dumps(data), content_type="application/json")
