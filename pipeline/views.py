from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from .forms import IntakeUploadForm


def upload_intake(request: HttpRequest) -> HttpResponse:
    form = IntakeUploadForm()

    if request.method == "POST":
        form = IntakeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # TODO: hand off files to the pipeline runner
            files = form.cleaned_data["files"]
            return render(
                request,
                "pipeline/upload.html",
                {"form": IntakeUploadForm(), "success": True, "file_count": len(files)},
            )

    return render(request, "pipeline/upload.html", {"form": form})
