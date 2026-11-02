import pytest
from django.core import mail
from rest_framework.test import APIClient
from accounts.models import Organization, Role, User
from expenses.models import ExpenseStatus
from expenses.services import transition, TransitionError, can_comment
from expenses.test_review_workflow import setup_review

pytestmark = pytest.mark.django_db

def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api

def test_routes_to_own_department_not_first_reviewer(setup_review, django_capture_on_commit_callbacks):
    org, users, expense = setup_review
    wrong = users[Role.REVIEWER]
    wrong.department = "Legal"
    wrong.save()
    right = User.objects.create_user(username="it-reviewer", email="it@example.test", role=Role.REVIEWER, department="IT", organization=org)
    with django_capture_on_commit_callbacks(execute=True):
        expense = transition(expense, users[Role.REQUESTER], "submit")
    assert expense.assigned_reviewer == right
    assert mail.outbox[-1].to == [right.email]
    assert client(wrong).get(f"/api/expenses/{expense.pk}/").status_code == 404
    assert transition(expense, right, "review").status == ExpenseStatus.SUBMITTED

@pytest.mark.parametrize("department", ["", "Legal"])
def test_no_fallback_to_other_department(setup_review, department, django_capture_on_commit_callbacks):
    org, users, expense = setup_review
    reviewer = users[Role.REVIEWER]
    reviewer.department = department
    reviewer.save()
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(TransitionError):
            transition(expense, users[Role.REQUESTER], "submit")
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.DRAFT
    assert expense.assigned_reviewer is None
    assert not mail.outbox

def test_expense_department_cannot_be_forged(setup_review):
    org, users, expense = setup_review
    api = client(users[Role.REQUESTER])
    url = f"/api/expenses/{expense.pk}/"
    assert api.patch(url, {"department": "Legal"}, format="json").status_code == 400
    expense.refresh_from_db()
    assert expense.department == "IT"
    expense.department = "Legal"
    expense.save()
    with pytest.raises(TransitionError):
        transition(expense, users[Role.REQUESTER], "submit")
    fixed = api.patch(url, {"title": "Fixed draft"}, format="json")
    assert fixed.status_code == 200 and fixed.data['department'] == "IT"

def test_create_uses_account_department_and_rejects_other_department(setup_review):
    org, users, expense = setup_review
    api = client(users[Role.REQUESTER])
    payload = {"title": "Travel", "branch": "Lagos", "items": [{"description": "Taxi", "quantity": "1", "unit_price": "100"}]}
    response = api.post('/api/expenses/', payload, format='json')
    assert response.status_code == 201 and response.data['department'] == "IT"
    response = api.post('/api/expenses/', {**payload, "department": "Legal"}, format='json')
    assert response.status_code == 400

def test_unassigned_user_cannot_create_or_submit(setup_review):
    org, users, expense = setup_review
    owner = users[Role.REQUESTER]
    owner.department = ""
    owner.save()
    with pytest.raises(TransitionError):
        transition(expense, owner, "submit")
    assert client(owner).patch(f"/api/expenses/{expense.pk}/", {"title": "Changed"}, format="json").status_code == 400

def test_reviewer_moved_department_loses_review_access(setup_review):
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    reviewer = users[Role.REVIEWER]
    reviewer.department = "Legal"
    reviewer.save()
    assert not can_comment(reviewer, expense)
    with pytest.raises(TransitionError):
        transition(expense, reviewer, "review")
    api = client(reviewer)
    for suffix in ['', 'history/', 'comments/', 'evidence/']:
        assert api.get(f"/api/expenses/{expense.pk}/{suffix}").status_code == 404

def test_admin_assigns_department_and_me_exposes_it(setup_review):
    org, users, expense = setup_review
    owner = users[Role.REQUESTER]
    response = client(users[Role.ADMIN]).patch(f"/api/organizations/{org.pk}/users/{owner.pk}/", {"department": "Legal"}, format='json')
    assert response.status_code == 200 and response.data['department'] == "Legal"
    owner.refresh_from_db()
    assert client(owner).get('/api/auth/me').data['department'] == "Legal"
    assert client(owner).patch(f"/api/organizations/{org.pk}/users/{owner.pk}/", {"department": "IT"}, format='json').status_code == 403

@pytest.mark.parametrize('department', ['', 'Unknown'])
def test_admin_cannot_assign_missing_or_unknown_department(setup_review, department):
    org, users, expense = setup_review
    payload = {"username": "new-user", "email": "new@example.test", "role": "REQUESTER", "department": department, "password": "Strong-New-Password-98!"}
    assert client(users[Role.ADMIN]).post('/api/auth/register', payload, format='json').status_code == 400

def test_reviewer_own_expense_still_goes_direct_to_approver(setup_review):
    org, users, expense = setup_review
    expense.created_by = users[Role.REVIEWER]
    expense.save()
    result = transition(expense, users[Role.REVIEWER], 'submit')
    assert result.status == ExpenseStatus.SUBMITTED and result.assigned_reviewer is None


def test_pending_review_reroute_is_previewed_and_scoped(setup_review):
    from django.core.management import call_command
    from io import StringIO
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    wrong = users[Role.REVIEWER]
    wrong.department = "Legal"
    wrong.save()
    right = User.objects.create_user(username="new-it", role=Role.REVIEWER, department="IT", organization=org)
    call_command("reroute_department_reviews", stdout=StringIO())
    expense.refresh_from_db()
    assert expense.assigned_reviewer == wrong
    call_command("reroute_department_reviews", apply=True, stdout=StringIO())
    expense.refresh_from_db()
    assert expense.assigned_reviewer == right and expense.status == ExpenseStatus.IN_REVIEW
    assert expense.history.latest().history_change_reason == "Pending review routed to department reviewer"


def test_pending_reroute_blocks_if_no_department_reviewer(setup_review):
    from django.core.management import call_command, CommandError
    from io import StringIO
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    users[Role.REVIEWER].department = "Legal"
    users[Role.REVIEWER].save()
    with pytest.raises(CommandError):
        call_command("reroute_department_reviews", apply=True, stdout=StringIO())
    expense.refresh_from_db()
    assert expense.assigned_reviewer == users[Role.REVIEWER]
