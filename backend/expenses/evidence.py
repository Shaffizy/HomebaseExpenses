from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework import serializers


def evidence_storage():
    return FileSystemStorage(location=settings.PRIVATE_EVIDENCE_ROOT)


def evidence_path(instance, filename):
    return f"{instance.expense.organization_id}/{instance.expense_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_document(file):
    if not file.size or file.size > settings.EVIDENCE_MAX_BYTES:
        raise serializers.ValidationError("File must be nonempty and no larger than 10 MB.")
    signatures = {".pdf": b"%PDF-", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}
    signature = signatures.get(Path(file.name).suffix.lower())
    header = file.read(8)
    file.seek(0)
    if signature is None or not header.startswith(signature):
        raise serializers.ValidationError("Upload a PDF, PNG, or JPEG file with matching file content.")
    return file
