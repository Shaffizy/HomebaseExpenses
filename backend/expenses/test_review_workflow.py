import pytest
from django.core import mail
from rest_framework.test import APIClient
from accounts.models import Organization, User, Role
from expenses.models import Expense, ExpenseItem, ExpenseStatus
from expenses.services import transition, TransitionError
from expenses.notifications import public_expense_url

pytestmark = pytest.mark.django_db

@pytest.fixture
def setup_review(settings):
    settings.EMAIL_TEST_MODE = False
    org = Organization.objects.create(name="Review bank")
    users = {role: User.objects.create_user(department="IT", username=role.lower(), email=f"{role.lower()}@example.test", organization=org, role=role, password="Original-Secret-432!") for role in Role.values}
    users["FINCON_REVIEWER"] = User.objects.create_user(department="FinCon", username="fincon-reviewer", email="fincon@example.test", organization=org, role=Role.REVIEWER, password="Original-Secret-432!")
    expense = Expense.objects.create(organization=org, created_by=users[Role.REQUESTER], expense_number="EXP-REVIEW", title="Supplies", department="IT", branch="Lagos", total="1000.00")
    ExpenseItem.objects.create(expense=expense, description="Paper", quantity=1, unit_price=1000)
    return org, users, expense

def test_requester_review_then_approval(setup_review, django_capture_on_commit_callbacks, settings):
    org, users, expense = setup_review
    settings.FRONTEND_URL = "http://10.10.5.133:3005"
    with django_capture_on_commit_callbacks(execute=True):
        expense = transition(expense, users[Role.REQUESTER], "submit")
    assert expense.status == ExpenseStatus.IN_REVIEW
    assert expense.assigned_reviewer == users[Role.REVIEWER]
    assert [m.to for m in mail.outbox] == [[users[Role.REQUESTER].email], [users[Role.REVIEWER].email]]
    assert "for your review" in mail.outbox[1].body
    assert "[TEST]" not in mail.outbox[0].subject
    assert public_expense_url(expense) in mail.outbox[0].body
    with pytest.raises(TransitionError):
        transition(expense, users[Role.APPROVER], "approve")
    with django_capture_on_commit_callbacks(execute=True):
        expense = transition(expense, users[Role.REVIEWER], "review")
    assert expense.status == ExpenseStatus.IN_FINCON_REVIEW
    assert expense.reviewed_by == users[Role.REVIEWER]
    assert expense.assigned_reviewer == users["FINCON_REVIEWER"]
    assert mail.outbox[-1].to == [users["FINCON_REVIEWER"].email]
    assert "for your FinCon review" in mail.outbox[-1].body
    with pytest.raises(TransitionError):
        transition(expense, users["FINCON_REVIEWER"], "review")
    with django_capture_on_commit_callbacks(execute=True):
        expense = transition(expense, users["FINCON_REVIEWER"], "review", wht_classification="RATE_2_NETWORK_DATA")
    assert expense.status == ExpenseStatus.SUBMITTED
    assert expense.fincon_reviewed_by == users["FINCON_REVIEWER"]
    assert str(expense.wht_rate) == "2.00"
    assert str(expense.wht_amount) == "20.00"
    assert str(expense.net_total) == "980.00"
    assert mail.outbox[-1].to == [users[Role.APPROVER].email]
    assert transition(expense, users[Role.APPROVER], "approve").status == ExpenseStatus.APPROVED

def test_reviewer_own_expense_skips_departmental_review_and_routes_to_fincon(setup_review):
    org, users, expense = setup_review
    expense.created_by = users[Role.REVIEWER]
    expense.save()
    expense = transition(expense, users[Role.REVIEWER], "submit")
    assert expense.status == ExpenseStatus.IN_FINCON_REVIEW
    assert expense.assigned_reviewer == users["FINCON_REVIEWER"]
    with pytest.raises(TransitionError):
        transition(expense, users[Role.REVIEWER], "review", wht_classification="NON_TAXABLE_0")
    expense = transition(expense, users["FINCON_REVIEWER"], "review", wht_classification="RATE_10_RENT_LEASE")
    assert expense.status == ExpenseStatus.SUBMITTED
    assert str(expense.wht_amount) == "100.00"
    assert str(expense.net_total) == "900.00"
    assert transition(expense, users[Role.APPROVER], "approve").status == ExpenseStatus.APPROVED

def test_fincon_reviewer_own_expense_calculates_wht_and_goes_to_approver(setup_review):
    org, users, expense = setup_review
    fincon = users["FINCON_REVIEWER"]
    expense.created_by = fincon
    expense.department = "FinCon"
    expense.save()
    expense = transition(expense, fincon, "submit")
    assert expense.status == ExpenseStatus.IN_FINCON_REVIEW
    assert expense.assigned_reviewer == fincon
    with pytest.raises(TransitionError):
        transition(expense, fincon, "return", comment="Cannot return to self")
    with pytest.raises(TransitionError):
        transition(expense, fincon, "reject", comment="Cannot reject self")
    expense = transition(expense, fincon, "review", wht_classification="RATE_5_PROFESSIONAL")
    assert expense.status == ExpenseStatus.SUBMITTED
    assert str(expense.wht_rate) == "5.00"
    assert str(expense.wht_amount) == "50.00"
    assert str(expense.net_total) == "950.00"
    assert transition(expense, users[Role.APPROVER], "approve").status == ExpenseStatus.APPROVED

@pytest.mark.parametrize("action", ["return", "reject"])
def test_review_decision_and_comment(setup_review, action):
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    with pytest.raises(TransitionError):
        transition(expense, users[Role.REVIEWER], action)
    expense = transition(expense, users[Role.REVIEWER], action, comment="Please correct the amount")
    assert expense.status == (ExpenseStatus.RETURNED if action == "return" else ExpenseStatus.REJECTED)
    assert expense.comments.count() == 1
    if action == "return":
        assert transition(expense, users[Role.REQUESTER], "submit").status == ExpenseStatus.IN_REVIEW

def test_other_reviewer_cannot_act_or_read(setup_review):
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    other = User.objects.create_user(username="other-reviewer", role=Role.REVIEWER, organization=org)
    with pytest.raises(TransitionError):
        transition(expense, other, "review")
    client = APIClient()
    client.force_authenticate(other)
    assert client.get(f"/api/expenses/{expense.pk}/").status_code == 404

def test_admin_username_and_password_reset(setup_review):
    org, users, expense = setup_review
    client = APIClient()
    client.force_authenticate(users[Role.ADMIN])
    owner = users[Role.REQUESTER]
    url = f"/api/organizations/{org.pk}/users/{owner.pk}/"
    response = client.patch(url, {"username": "new-login", "password": "Replacement-Strong-982!"}, format="json")
    assert response.status_code == 200, response.data
    assert "password" not in response.data
    owner.refresh_from_db()
    assert owner.username == "new-login"
    assert owner.check_password("Replacement-Strong-982!")
    client.force_authenticate(users[Role.REVIEWER])
    assert client.patch(url, {"username": "blocked"}, format="json").status_code == 403

def test_reviewer_can_create_expense(setup_review):
    org, users, expense = setup_review
    client = APIClient()
    client.force_authenticate(users[Role.REVIEWER])
    response = client.post("/api/expenses/", {"title": "Reviewer travel", "department": "IT", "branch": "Lagos", "items": [{"description": "Taxi", "quantity": "1", "unit_price": "100"}]}, format="json")
    assert response.status_code == 201, response.data
    assert client.post(f"/api/expenses/{response.data['id']}/submit/").data['status'] == "IN_FINCON_REVIEW"


def test_logging_in_other_accounts_does_not_approve_expense(setup_review):
    org, users, expense = setup_review
    expense = transition(expense, users[Role.REQUESTER], "submit")
    expense = transition(expense, users[Role.REVIEWER], "review")
    expense = transition(expense, users["FINCON_REVIEWER"], "review", wht_classification="NON_TAXABLE_0")
    history_count = expense.history.count()
    browsers = {}
    for role in (Role.REQUESTER, Role.APPROVER):
        browser = APIClient()
        login = browser.post('/api/auth/login', {'username': users[role].username, 'password': 'Original-Secret-432!'}, format='json')
        assert login.status_code == 200, login.data
        browser.credentials(HTTP_AUTHORIZATION='Bearer ' + login.data['access'])
        assert browser.get('/api/auth/me').data['id'] == users[role].pk
        browsers[role] = browser
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.SUBMITTED
    assert expense.approved_by is None and expense.approved_at is None
    assert expense.history.count() == history_count
    assert browsers[Role.REQUESTER].post(f'/api/expenses/{expense.pk}/approve/').status_code == 403
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.SUBMITTED
    assert browsers[Role.APPROVER].post(f'/api/expenses/{expense.pk}/approve/').status_code == 200
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.APPROVED and expense.approved_by == users[Role.APPROVER]
