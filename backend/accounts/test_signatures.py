import base64
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, PngImagePlugin
from rest_framework.test import APIClient

from accounts.models import Organization, Role, User
from expenses.models import Expense, ExpenseCategory, ExpenseItem
from expenses.services import transition

PASSWORD = "Secure-Signature-432!"
URL = "/api/auth/signature"


def client(user):
    result = APIClient()
    result.force_authenticate(user)
    return result


def image_file(color="black", format="PNG", size=(200, 70)):
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "remove me")
    Image.new("RGB", size, color).save(output, format=format, **({"pnginfo": metadata} if format == "PNG" else {}))
    return SimpleUploadedFile("signature." + format.lower(), output.getvalue(), content_type="image/" + format.lower())


def upload(user, **overrides):
    return client(user).post(URL, {"file": image_file(), "current_password": PASSWORD, **overrides}, format="multipart")


@pytest.fixture
def people(db):
    org = Organization.objects.create(name="Signature tests")
    return {role: User.objects.create_user(username=role.lower(), organization=org, role=role, password=PASSWORD) for role in Role.values}


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_signature_requires_auth(people, method):
    assert getattr(APIClient(), method)(URL).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["REQUESTER", "ADMIN"])
@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_only_approver_can_manage_signature(people, role, method):
    assert getattr(client(people[role]), method)(URL).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_upload_normalizes_image_and_strips_metadata(people, format):
    approver = people["APPROVER"]
    result = upload(approver, file=image_file(format=format))
    assert result.status_code == 200, result.data
    approver.refresh_from_db()
    data = approver.signature_data
    assert data.startswith("data:image/png;base64,")
    normalized = Image.open(BytesIO(base64.b64decode(data.split(",")[1])))
    assert normalized.format == "PNG" and "private" not in normalized.info
    assert client(approver).get(URL).data["signature_data"] == data
    assert "signature_data" not in client(approver).get("/api/auth/me").data


@pytest.mark.django_db
def test_password_required_for_changes(people):
    approver = people["APPROVER"]
    assert upload(approver, current_password="wrong").status_code == 400
    assert upload(approver).status_code == 200
    approver.refresh_from_db()
    original = approver.signature_data
    assert client(approver).delete(URL, {"current_password": "wrong"}, format="json").status_code == 400
    approver.refresh_from_db()
    assert approver.signature_data == original
    assert client(approver).delete(URL, {"current_password": PASSWORD}, format="json").status_code == 204
    approver.refresh_from_db()
    assert approver.signature_data == ""


@pytest.mark.django_db
@pytest.mark.parametrize("bad", ["svg", "corrupt", "oversize", "dimensions"])
def test_invalid_image_rejected(people, bad):
    if bad == "svg":
        file = SimpleUploadedFile("signature.svg", b'<svg onload="alert(1)"/>', content_type="image/svg+xml")
    elif bad == "corrupt":
        file = SimpleUploadedFile("signature.png", b"not an image", content_type="image/png")
    elif bad == "oversize":
        file = SimpleUploadedFile("signature.png", b"x" * (1024 * 1024 + 1), content_type="image/png")
    else:
        file = image_file(size=(2001, 40))
    assert upload(people["APPROVER"], file=file).status_code == 400
    people["APPROVER"].refresh_from_db()
    assert people["APPROVER"].signature_data == ""


@pytest.mark.django_db
def test_cannot_target_another_approver(people):
    org = Organization.objects.create(name="Other signatures")
    other = User.objects.create_user(username="other", organization=org, role=Role.APPROVER, password=PASSWORD)
    assert upload(people["APPROVER"], user_id=other.pk).status_code == 200
    other.refresh_from_db()
    assert other.signature_data == ""


@pytest.mark.django_db
def test_approval_snapshot_is_immutable_and_scoped(people):
    requester, approver, admin = people["REQUESTER"], people["APPROVER"], people["ADMIN"]
    assert upload(approver).status_code == 200
    approver.refresh_from_db()
    original = approver.signature_data
    category = ExpenseCategory.objects.create(organization=requester.organization, name="Equipment", created_by=admin)
    expense = Expense.objects.create(organization=requester.organization, created_by=requester, expense_number="EXP-SIGN", title="Office equipment", category=category, department="IT", branch="Lagos", total="20.00")
    ExpenseItem.objects.create(expense=expense, description="Paper", quantity=2, unit_price=10)
    assert client(requester).patch(f"/api/expenses/{expense.pk}/", {"approved_signature_data": "forged"}, format="json").status_code == 200
    expense.refresh_from_db()
    assert expense.approved_signature_data == ""
    expense = transition(expense, requester, "submit")
    expense = transition(expense, approver, "approve")
    assert expense.approved_signature_data == original
    assert upload(approver, file=image_file("blue")).status_code == 200
    assert client(approver).delete(URL, {"current_password": PASSWORD}, format="json").status_code == 204
    expense.refresh_from_db()
    assert expense.approved_signature_data == original
    for user in people.values():
        result = client(user).get(f"/api/expenses/{expense.pk}/")
        assert result.status_code == 200
        assert result.data["approved_signature_data"] == original
        rows = client(user).get("/api/expenses/").data["results"]
        assert "approved_signature_data" not in rows[0]
    history = client(requester).get(f"/api/expenses/{expense.pk}/history/").data
    assert original not in str(history)
    org = Organization.objects.create(name="Outside")
    outsider = User.objects.create_user(username="outsider", organization=org, role=Role.APPROVER, password=PASSWORD)
    assert client(outsider).get(f"/api/expenses/{expense.pk}/").status_code == 404
    another = User.objects.create_user(username="another", organization=requester.organization, role=Role.REQUESTER, password=PASSWORD)
    assert client(another).get(f"/api/expenses/{expense.pk}/").status_code == 404
