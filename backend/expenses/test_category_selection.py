import pytest
from expenses.test_workflow import setup, api
from expenses.models import Expense

pytestmark = pytest.mark.django_db

def test_saved_category_and_custom_expense_name_stay_distinct(setup):
    org, users, expense = setup
    response = api(users["REQUESTER"]).post("/api/expenses/", {"title": "Taxi for client visit", "category": expense.category_id, "branch": "Lagos", "items": [{"description": "Taxi", "quantity": "1", "unit_price": "100"}]}, format="json")
    assert response.status_code == 201, response.data
    assert response.data['title'] == 'Taxi for client visit'
    assert response.data['expense_category_name'] == expense.category.name
    assert response.data['category'] == expense.category_id
    assert Expense.objects.get(pk=response.data['id']).category_id == expense.category_id


def test_editing_an_inactive_category_expense_preserves_category(setup):
    org, users, expense = setup
    expense.category.is_active = False
    expense.category.save()
    response = api(users["REQUESTER"]).patch(f"/api/expenses/{expense.pk}/", {"title": "Updated expense"}, format="json")
    assert response.status_code == 200, response.data
    assert response.data['category'] == expense.category_id
    assert response.data['expense_category_name'] == expense.category.name
