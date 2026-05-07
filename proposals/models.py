import uuid

from django.db import models

from pipeline.models import RunRecord


class ProposalRecord(models.Model):

    class Status(models.TextChoices):
        PENDING  = "pending",  "Pending"
        RUNNING  = "running",  "Running"
        COMPLETE = "complete", "Complete"
        FAILED   = "failed",   "Failed"

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run           = models.OneToOneField(
                        RunRecord,
                        on_delete=models.CASCADE,
                        related_name="proposal",
                    )
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    output_json   = models.TextField(blank=True)
    docx_path     = models.CharField(max_length=500, blank=True)
    raw_output    = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Proposal for Run {self.run_id} [{self.status}]"
