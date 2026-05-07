from django.urls import path
from . import views

app_name = "pipeline"

urlpatterns = [
    path("", views.upload_intake, name="upload"),
    path("run/<uuid:run_id>/", views.run_status, name="run_status"),
    path("run/<uuid:run_id>/stream/", views.run_stream, name="run_stream"),
]
