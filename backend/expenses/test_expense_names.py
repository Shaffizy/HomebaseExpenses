import pytest
from expenses.models import Expense, ExpenseCategory
from expenses.test_workflow import setup, api


def payload(**overrides):
    values = {"title": "  Replace broken keyboards  ", "department": "IT", "branch": "Lagos",
              "items": [{"description": "Keyboard", "quantity": "2", "unit_price": "15000.00"}]}
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_requester_creates_edits_and_submits_without_categories(setup):
    org, users, existing = setup
    existing.delete()
    ExpenseCategory.objects.all().delete()
    client = api(users["REQUESTER"])
    created = client.post('/api/expenses/', payload(), format='json')
    assert created.status_code == 201, created.data
    assert created.data['title'] == created.data['category_name'] == 'Replace broken keyboards'
    assert created.data['category'] is None and created.data['total'] == '30000.00'
    url = f"/api/expenses/{created.data['id']}/"
    changed = client.patch(url, {'title': 'New office keyboards'}, format='json')
    assert changed.status_code == 200 and changed.data['title'] == 'New office keyboards'
    listed = client.get('/api/expenses/', {'search': 'New office keyboards'})
    assert listed.status_code == 200 and listed.data['count'] == 1
    submitted = client.post(url + 'submit/', {}, format='json')
    assert submitted.status_code == 200 and submitted.data['status'] == 'SUBMITTED'
    assert client.patch(url, {'title': 'Late edit'}, format='json').status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('title', ['', '   ', None, 'x' * 256])
def test_invalid_expense_names_rejected(setup, title):
    org, users, expense = setup
    response = api(users['REQUESTER']).post('/api/expenses/', payload(title=title), format='json')
    assert response.status_code == 400 and 'title' in response.data


@pytest.mark.django_db
def test_blank_name_blocks_submission_even_when_category_exists(setup):
    org, users, expense = setup
    expense.title = '   '
    expense.save()
    response = api(users['REQUESTER']).post(f'/api/expenses/{expense.pk}/submit/', {}, format='json')
    assert response.status_code == 400
    expense.refresh_from_db()
    assert expense.status == 'DRAFT'


@pytest.mark.django_db
def test_name_wins_over_legacy_category_and_appears_in_email(setup, django_capture_on_commit_callbacks):
    from django.core import mail
    org, users, expense = setup
    client = api(users['REQUESTER'])
    updated = client.patch(f'/api/expenses/{expense.pk}/', {'title': 'Replace faulty router'}, format='json')
    assert updated.status_code == 200
    assert updated.data['category_name'] == 'Replace faulty router'
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(f'/api/expenses/{expense.pk}/submit/', {}, format='json')
    assert response.status_code == 200
    assert len(mail.outbox) == 2
    assert all('Replace faulty router' in message.body for message in mail.outbox)
