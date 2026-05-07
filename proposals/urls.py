from django.urls import path

from . import views

app_name = "proposals"

urlpatterns = [
    path(
        "run/<uuid:run_id>/proposal/stream/",
        views.proposal_stream,
        name="proposal_stream",
    ),
    path(
        "run/<uuid:run_id>/proposal/download/",
        views.proposal_download_docx,
        name="proposal_download",
    ),
    path(
        "run/<uuid:run_id>/proposal/status/",
        views.proposal_status_json,
        name="proposal_status",
    ),
]
