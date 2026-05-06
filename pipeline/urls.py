from django.urls import path
from . import views

app_name = "pipeline"

urlpatterns = [
    path("", views.upload_intake, name="upload"),
]
