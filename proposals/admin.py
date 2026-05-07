from django.contrib import admin

from .models import ProposalRecord


@admin.register(ProposalRecord)
class ProposalRecordAdmin(admin.ModelAdmin):
    list_display    = ["id", "run", "status", "created_at"]
    list_filter     = ["status"]
    readonly_fields = ["id", "run", "created_at", "updated_at", "raw_output"]
