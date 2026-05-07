from django import forms

ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx", ".md"]


class IntakeUploadForm(forms.Form):
    """Thin form — only provides CSRF. File validation is done in the view
    so we can handle multi-file uploads without fighting Django's FileField."""
    pass
