from unittest.mock import patch

import pytest
from django.core import mail
from django.db import transaction

from accounts.models import Organization, Role, User
from expenses.models import Expense, ExpenseCategory, ExpenseItem
from expenses.services import transition, TransitionError


@pytest.fixture
def ticket(db):
    org = Organization.objects.create(name="Homebase")
    owner = User.objects.create_user(username="owner", email="owner@example.test", organization=org, role=Role.REQUESTER)
    approver = User.objects.create_user(username="approver", email="approver@example.test", organization=org, role=Role.APPROVER)
    category = ExpenseCategory.objects.create(organization=org, name="Supplies <script>bad()</script>", created_by=owner)
    expense = Expense.objects.create(organization=org, created_by=owner, expense_number="EXP-MAIL", title="Supplies <script>bad()</script>", category=category, department="IT", branch="Lagos", total="20.00")
    ExpenseItem.objects.create(expense=expense, description="Paper", quantity=2, unit_price=10)
    User.objects.create_user(username="reviewer", email="reviewer@example.test", organization=org, role=Role.REVIEWER)
    return expense, owner, approver


def test_submission_sends_two_private_messages(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, owner, "submit")
        assert len(mail.outbox) == 0
    assert len(mail.outbox) == 2
    assert mail.outbox[0].to == [owner.email]
    assert mail.outbox[1].to == ["reviewer@example.test"]
    assert "submitted successfully" in mail.outbox[0].subject
    assert "requires your review" in mail.outbox[1].subject
    assert "NGN 20.00" in mail.outbox[0].body
    assert "&lt;script&gt;" in mail.outbox[0].alternatives[0].content
    assert "<script>" not in mail.outbox[0].alternatives[0].content
    assert mail.outbox[0].from_email == mail.outbox[1].from_email


def test_draft_edits_and_denied_actions_do_not_send(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    with django_capture_on_commit_callbacks(execute=True):
        expense.save()
        with pytest.raises(TransitionError):
            transition(expense, approver, "submit")
    assert len(mail.outbox) == 0


def test_rollback_does_not_send(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            transition(expense, owner, "submit")
            raise RuntimeError("rollback")
    expense.refresh_from_db()
    assert expense.status == "DRAFT"
    assert len(mail.outbox) == 0


def test_no_cross_organization_notification(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    org = Organization.objects.create(name="Other")
    outsider = User.objects.create_user(username="outsider", organization=org, role=Role.REQUESTER)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(TransitionError):
            transition(expense, outsider, "submit")
    assert len(mail.outbox) == 0


def test_mail_failure_keeps_submission_and_attempts_other_recipient(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    with patch("expenses.notifications.EmailMultiAlternatives.send", side_effect=[OSError("offline"), 1]) as send:
        with django_capture_on_commit_callbacks(execute=True):
            transition(expense, owner, "submit")
    expense.refresh_from_db()
    assert expense.status == "IN_REVIEW"
    assert send.call_count == 2


def test_repeated_submit_does_not_duplicate_mail(ticket, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, owner, "submit")
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(TransitionError):
            transition(expense, owner, "submit")
    assert len(mail.outbox) == 2


@pytest.mark.parametrize("action", ["approve", "return", "reject"])
def test_decisions_notify_requester_from_application_sender(ticket, django_capture_on_commit_callbacks, settings, action):
    expense, owner, approver = ticket
    with django_capture_on_commit_callbacks(execute=True):
        expense = transition(expense, owner, "submit")
        expense = transition(expense, User.objects.get(username="reviewer"), "review")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, approver, action, comment="Reason")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [owner.email]
    assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL


def test_old_personal_mailboxes_never_override_registered_address(ticket, django_capture_on_commit_callbacks):
    from accounts.models import ConnectedMailbox
    expense, owner, approver = ticket
    ConnectedMailbox.objects.create(user=owner, organization=owner.organization,
        provider="gmail", email="old-personal@example.test", encrypted_token="retired")
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, owner, "submit")
    assert mail.outbox[0].to == [owner.email]


@pytest.mark.parametrize("base", ["http://127.0.0.1:5174", "https://127.0.0.1", "https://localhost", "https://[::1]", "javascript:alert(1)"])
def test_email_omits_local_private_or_unsafe_links(ticket, settings, django_capture_on_commit_callbacks, base):
    expense, owner, approver = ticket
    settings.FRONTEND_URL = base
    settings.EMAIL_TEST_MODE = True
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, owner, "submit")
    for message in mail.outbox:
        assert base not in message.body
        assert 'href=' not in message.alternatives[0].content
        assert message.subject.startswith("[TEST] ")
        assert "not a production bank notification" in message.body


def test_public_https_deployment_link_and_production_label(ticket, settings, django_capture_on_commit_callbacks):
    expense, owner, approver = ticket
    settings.FRONTEND_URL = "https://expenses.homebasebank.com"
    settings.EMAIL_TEST_MODE = False
    with django_capture_on_commit_callbacks(execute=True):
        transition(expense, owner, "submit")
    assert f'https://expenses.homebasebank.com/expenses/{expense.pk}' in mail.outbox[0].body
    assert not mail.outbox[0].subject.startswith("[TEST]")
