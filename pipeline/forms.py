from django import forms
from django.forms.widgets import FileInput


ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx", ".md"]


class MultiFileInput(FileInput):
    """FileInput that accepts multiple files (Django 6 blocks this by default)."""

    def __init__(self, attrs=None):
        # Bypass Django's multiple-file guard by calling Widget.__init__ directly
        forms.Widget.__init__(self, attrs)

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files


class IntakeUploadForm(forms.Form):
    files = forms.FileField(
        widget=MultiFileInput(attrs={"multiple": True, "accept": ".pdf,.doc,.docx,.md"}),
        label="Intake Documents",
        help_text="Upload .pdf, .doc, .docx, or .md files.",
    )

    def clean_files(self):
        uploaded = self.files.getlist("files")
        if not uploaded:
            raise forms.ValidationError("Please upload at least one file.")

        errors = []
        for f in uploaded:
            name = f.name.lower()
            if not any(name.endswith(ext) for ext in ACCEPTED_EXTENSIONS):
                errors.append(
                    forms.ValidationError(
                        '"%(name)s" is not supported. Accepted: %(types)s',
                        params={"name": f.name, "types": ", ".join(ACCEPTED_EXTENSIONS)},
                        code="invalid_type",
                    )
                )

        if errors:
            raise forms.ValidationError(errors)

        return uploaded
