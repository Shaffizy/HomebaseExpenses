import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from accounts.models import Organization, Role, User
from expenses.models import Expense, ExpenseItem, ExpenseStatus, Comment, ExpenseCategory
from expenses.services import transition, TransitionError

@pytest.fixture
def setup(db):
    org = Organization.objects.create(name="Homebase Mortgage Bank")
    users = {}
    for role in Role.values:
        users[role] = User.objects.create_user(username=role.lower(), email=f"{role.lower()}@example.test", organization=org, role=role, password="Test-Secret-4321!")
    category = ExpenseCategory.objects.create(organization=org, name="Office supplies", created_by=users["ADMIN"])
    expense = Expense.objects.create(organization=org, created_by=users["REQUESTER"], expense_number="EXP-1", title="Office supplies", category=category, department="IT", branch="Lagos")
    ExpenseItem.objects.create(expense=expense, description="Paper", quantity=2, unit_price=10)
    return org, users, expense

def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client

@pytest.mark.django_db
@pytest.mark.parametrize("role", ["REQUESTER", "APPROVER", "ADMIN"])
@pytest.mark.parametrize("status", ExpenseStatus.values)
@pytest.mark.parametrize("action", ["submit", "approve", "return", "reject"])
def test_workflow_matrix(setup, role, status, action):
    org, users, expense = setup
    expense.status = status
    expense.save()
    allowed = (role == "REQUESTER" and action == "submit" and status in ["DRAFT", "RETURNED"]) or (role == "APPROVER" and action in ["approve", "return", "reject"] and status == "SUBMITTED")
    result = api(users[role]).post(f"/api/expenses/{expense.pk}/{action}/", {"comment": "Reason"}, format="json")
    assert result.status_code == (200 if allowed else 403 if role == "ADMIN" or (role == "REQUESTER" and action != "submit") or (role == "APPROVER" and action == "submit") else 409), result.data

@pytest.mark.django_db
def test_single_approver_constraint(setup):
    org, users, expense = setup
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(username="second", organization=org, role=Role.APPROVER)
    other = User.objects.create(username="inactive", organization=org, role=Role.APPROVER, is_active=False)
    with pytest.raises(IntegrityError), transaction.atomic():
        other.is_active = True
        other.save()

@pytest.mark.django_db
def test_admin_registration_and_privileges(setup):
    org, users, expense = setup
    payload = {"username": "newrequester", "email": "new@example.test", "role": "REQUESTER", "password": "Secure-New-43!"}
    assert api(users["REQUESTER"]).post("/api/auth/register", payload, format="json").status_code == 403
    assert api(users["ADMIN"]).post("/api/auth/register", payload, format="json").status_code == 201
    new = User.objects.get(username="newrequester")
    assert not new.is_staff and new.check_password(payload["password"])
    payload.update(username="secondapprover", role="APPROVER")
    assert api(users["ADMIN"]).post("/api/auth/register", payload, format="json").status_code == 400
    url = f"/api/organizations/{org.pk}/users/{new.pk}/"
    assert api(users["ADMIN"]).patch(url, {"role": "ADMIN"}, format="json").status_code == 400
    assert api(users["ADMIN"]).delete(f"/api/organizations/{org.pk}/users/{new.pk}/delete/").status_code == 204
    new.refresh_from_db()
    assert not new.is_active

@pytest.mark.django_db
def test_owner_edit_submit_and_scope(setup):
    org, users, expense = setup
    other = User.objects.create(username="other", organization=org, role=Role.REQUESTER)
    assert api(other).patch(f"/api/expenses/{expense.pk}/", {"title": "Tamper"}, format="json").status_code == 404
    assert api(other).post(f"/api/expenses/{expense.pk}/submit/", {}, format="json").status_code == 404
    assert api(users["ADMIN"]).patch(f"/api/expenses/{expense.pk}/", {"title": "Tamper"}, format="json").status_code == 403
    assert api(users["REQUESTER"]).post(f"/api/expenses/{expense.pk}/submit/", {}, format="json").status_code == 200
    assert api(users["REQUESTER"]).patch(f"/api/expenses/{expense.pk}/", {"title": "Late edit"}, format="json").status_code == 403
    elsewhere = Organization.objects.create(name="Other organization")
    outsider = User.objects.create(username="outsider", organization=elsewhere, role=Role.APPROVER)
    assert api(outsider).get(f"/api/expenses/{expense.pk}/").status_code == 404

@pytest.mark.django_db
def test_comment_reuse_and_approval_fields(setup):
    org, users, expense = setup
    owner, approver = api(users["REQUESTER"]), api(users["APPROVER"])
    result = owner.patch(f"/api/expenses/{expense.pk}/", {"approved_by": users["REQUESTER"].pk, "approved_at": "2020-01-01T00:00:00Z", "status": "APPROVED"}, format="json")
    assert result.status_code == 200
    expense.refresh_from_db()
    assert expense.approved_by is None and expense.approved_at is None and expense.status == "DRAFT"
    owner.post(f"/api/expenses/{expense.pk}/submit/", {}, format="json")
    assert api(users["REVIEWER"]).post(f"/api/expenses/{expense.pk}/review/", {}, format="json").status_code == 200
    assert approver.post(f"/api/expenses/{expense.pk}/return/", {}, format="json").status_code == 400
    assert approver.post(f"/api/expenses/{expense.pk}/comments/", {"text": "Attach the receipt"}, format="json").status_code == 201
    assert approver.post(f"/api/expenses/{expense.pk}/return/", {}, format="json").status_code == 200
    assert expense.comments.count() == 1
    owner.post(f"/api/expenses/{expense.pk}/submit/", {}, format="json")
    assert api(users["REVIEWER"]).post(f"/api/expenses/{expense.pk}/review/", {}, format="json").status_code == 200
    assert approver.post(f"/api/expenses/{expense.pk}/return/", {}, format="json").status_code == 400
    assert approver.post(f"/api/expenses/{expense.pk}/approve/", {}, format="json").status_code == 200
    expense.refresh_from_db()
    assert expense.approved_by == users["APPROVER"] and expense.approved_at is not None

@pytest.mark.django_db
def test_forward_removed_and_missing_approver(setup):
    org, users, expense = setup
    assert api(users["APPROVER"]).post(f"/api/expenses/{expense.pk}/forward/", {}, format="json").status_code == 404
    users["APPROVER"].is_active = False
    users["APPROVER"].save()
    assert api(users["REQUESTER"]).post(f"/api/expenses/{expense.pk}/submit/", {}, format="json").status_code == 409

@pytest.mark.django_db
def test_login_me_and_failed_login(setup):
    org, users, expense = setup
    client = APIClient()
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", {"username": "requester", "password": "wrong"}, format="json").status_code == 401
    response = client.post("/api/auth/login", {"username": "requester@example.test", "password": "Test-Secret-4321!"}, format="json")
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
    assert client.get("/api/auth/me").data["role"] == "REQUESTER"

@pytest.mark.django_db
def test_create_and_totals_and_negative_amounts(setup):
    org, users, expense = setup
    payload = {"title": "Printer paper", "department": "IT", "branch": "Lagos", "currency": "NGN", "items": [{"description": "Paper", "quantity": "2", "unit_price": "125.50"}]}
    for role in ["APPROVER", "ADMIN"]:
        assert api(users[role]).post("/api/expenses/", payload, format="json").status_code == 403
    result = api(users["REQUESTER"]).post("/api/expenses/", payload, format="json")
    assert result.status_code == 201 and result.data["total"] == "251.00"
    payload["items"][0]["unit_price"] = "-1"
    assert api(users["REQUESTER"]).post("/api/expenses/", payload, format="json").status_code == 400

@pytest.mark.django_db
def test_evidence_optional_and_private(setup, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    settings.PRIVATE_EVIDENCE_ROOT = str(tmp_path)
    org, users, expense = setup
    url = f"/api/expenses/{expense.pk}/evidence/"
    file = lambda: SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 receipt")
    assert api(users["ADMIN"]).post(url, {"category": "INVOICE_RECEIPT", "file": file()}, format="multipart").status_code == 403
    assert api(users["REQUESTER"]).post(url, {"category": "OTHER", "file": file()}, format="multipart").status_code == 400
    posted = api(users["REQUESTER"]).post(url, {"category": "OTHER", "label": "Receipt", "file": file()}, format="multipart")
    assert posted.status_code == 201
    assert "file" not in posted.data
    download = api(users["APPROVER"]).get(f"{url}{posted.data['id']}/")
    assert download.status_code == 200
    assert b"".join(download.streaming_content).startswith(b"%PDF-")
    api(users["REQUESTER"]).post(f"/api/expenses/{expense.pk}/submit/", {}, format="json")
    assert api(users["REQUESTER"]).delete(f"{url}{posted.data['id']}/").status_code == 403
    other = Organization.objects.create(name="Elsewhere")
    outsider = User.objects.create(username="evidence-outsider", role=Role.REQUESTER, organization=other)
    assert api(outsider).get(f"{url}{posted.data['id']}/").status_code == 404
