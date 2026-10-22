import pytest
from accounts.models import Organization, User, Role
from expenses.models import ExpenseCategory, Expense
from expenses.test_workflow import setup, api

def data(expense, **overrides):
    result = {"title": expense.title, "category": expense.category_id, "department": "IT", "branch": "Lagos", "items": [{"description": "Paper", "quantity": "2", "unit_price": "12.50"}]}
    result.update(overrides)
    return result

@pytest.mark.django_db
@pytest.mark.parametrize("role", ["REQUESTER", "APPROVER"])
def test_only_admin_manages_categories(setup, role):
    org, users, expense = setup
    client = api(users[role])
    assert client.get("/api/expense-categories/").status_code == 200
    assert client.post("/api/expense-categories/", {"name": "Travel"}, format="json").status_code == 403
    url = f"/api/expense-categories/{expense.category_id}/"
    assert client.patch(url, {"name": "Fake"}, format="json").status_code == 403
    assert client.delete(url).status_code == 403

@pytest.mark.django_db
def test_admin_create_edit_deactivate_and_duplicate(setup):
    org, users, expense = setup
    client = api(users["ADMIN"])
    response = client.post("/api/expense-categories/", {"name": " Travel "}, format="json")
    assert response.status_code == 201 and response.data["name"] == "Travel"
    assert client.post("/api/expense-categories/", {"name": "travel"}, format="json").status_code == 400
    url = f"/api/expense-categories/{response.data['id']}/?include_inactive=1"
    assert client.patch(url, {"name": "Transport", "is_active": False}, format="json").status_code == 200
    assert len(client.get("/api/expense-categories/?include_inactive=1").data) == 2
    assert len(api(users["REQUESTER"]).get("/api/expense-categories/").data) == 1
    assert client.patch(url, {"is_active": True}, format="json").status_code == 200

@pytest.mark.django_db
def test_category_scoped_to_organization(setup):
    org, users, expense = setup
    other = Organization.objects.create(name="Other")
    admin = User.objects.create(username="otheradmin", organization=other, role=Role.ADMIN)
    category = ExpenseCategory.objects.create(name="Other travel", organization=other, created_by=admin)
    assert api(users["REQUESTER"]).post("/api/expenses/", data(expense, category=category.pk), format="json").status_code == 400
    assert api(users["ADMIN"]).patch(f"/api/expense-categories/{category.pk}/", {"name": "Hijack"}, format="json").status_code == 404
    assert api(admin).get("/api/expense-categories/").data[0]["id"] == category.pk

@pytest.mark.django_db
@pytest.mark.parametrize("overrides", [
    {"category": 999999}, {"category": {"name": "Invented"}},
    {"department": "Invented department"}, {"branch": "Port Harcourt"},
])
def test_invalid_controlled_fields_rejected(setup, overrides):
    org, users, expense = setup
    assert api(users["REQUESTER"]).post("/api/expenses/", data(expense, **overrides), format="json").status_code == 400

@pytest.mark.django_db
def test_required_name_and_controlled_department_branch(setup):
    org, users, expense = setup
    client = api(users["REQUESTER"])
    for field in ["title", "department", "branch"]:
        payload = data(expense)
        del payload[field]
        assert client.post("/api/expenses/", payload, format="json").status_code == 400
    response = client.post("/api/expenses/", data(expense, title="Invented category", vendor_name="Invented department"), format="json")
    assert response.status_code == 201
    assert response.data["title"] == response.data["category_name"] == "Invented category"
    assert response.data["department"] == "IT"

@pytest.mark.django_db
def test_inactive_legacy_category_does_not_block_named_expense_submission(setup):
    org, users, expense = setup
    category = expense.category
    category.is_active = False
    category.save()
    client = api(users["REQUESTER"])
    assert client.post("/api/expenses/", data(expense), format="json").status_code == 400
    assert client.post(f"/api/expenses/{expense.pk}/submit/", {}, format="json").status_code == 200
    assert client.get(f"/api/expenses/{expense.pk}/").status_code == 200

@pytest.mark.django_db
def test_options_and_line_totals(setup):
    org, users, expense = setup
    client = api(users["REQUESTER"])
    options = client.get("/api/expenses/options/").data
    assert [d["value"] for d in options["departments"]] == ["IT", "Internal Control", "FinCon", "Marketing", "Human Resources", "Risk Control", "Legal", "Operation"]
    assert [b["value"] for b in options["branches"]] == ["Lagos", "Abuja"]
    items = [{"description": "A", "quantity": "0.50", "unit_price": "0.01"}, {"description": "B", "quantity": "0.50", "unit_price": "0.01"}]
    response = client.post("/api/expenses/", data(expense, items=items, total="9999"), format="json")
    assert response.status_code == 201, response.data
    assert [item["line_total"] for item in response.data["items"]] == ["0.01", "0.01"]
    assert response.data["total"] == "0.02"

@pytest.mark.django_db
def test_legacy_record_preserved_but_not_submittable(setup):
    org, users, expense = setup
    legacy = Expense.objects.create(organization=org, created_by=users["REQUESTER"], expense_number="OLD-1", title="Old title", vendor_name="Old vendor")
    client = api(users["REQUESTER"])
    response = client.get(f"/api/expenses/{legacy.pk}/")
    assert response.status_code == 200 and response.data["category_name"] == "Old title"
    assert client.post(f"/api/expenses/{legacy.pk}/submit/", {}, format="json").status_code == 400
