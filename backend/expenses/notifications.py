"""Homebase expense workflow mail, delivered only after a committed transition."""

import logging
import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from accounts.models import Role
from .models import ExpenseStatus

logger = logging.getLogger(__name__)


def public_expense_url(expense):
    base = settings.FRONTEND_URL.rstrip('/')
    try:
        URLValidator(schemes=["https"])(base)
        parsed = urlsplit(base)
        host = (parsed.hostname or "").lower().rstrip('.')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return ""
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid", ".lan", ".home")):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        return f"{base}/expenses/{expense.pk}"
    except (ValidationError, ValueError):
        return ""


def notify_next_role(expense):
    if expense.status not in {ExpenseStatus.SUBMITTED, ExpenseStatus.APPROVED, ExpenseStatus.RETURNED, ExpenseStatus.REJECTED}:
        return
    requester = expense.created_by
    approver = expense.assigned_approver
    if (approver is None or not approver.is_active or approver.role != Role.APPROVER
            or approver.organization_id != expense.organization_id
            or requester.organization_id != expense.organization_id):
        logger.error("Invalid notification routing for expense %s", expense.pk)
        return
    context = {
        "number": expense.expense_number,
        "requester": requester.get_full_name() or requester.username,
        "approver": approver.get_full_name() or approver.username,
        "category": expense.title or (expense.category.name if expense.category else "Untitled expense"),
        "department": expense.department,
        "branch": expense.branch,
        "total": f"{expense.total:,.2f}",
        "url": public_expense_url(expense),
        "test_mode": settings.EMAIL_TEST_MODE,
    }
    # Separate messages keep recipients private and allow one delivery to fail
    # without preventing the other recipient's notification.
    submitted = expense.status == ExpenseStatus.SUBMITTED
    recipients = ((requester, True), (approver, False)) if submitted else ((requester, False),)
    for recipient, confirmation in recipients:
        address = recipient.email
        if not address:
            logger.warning("Missing notification email for expense %s user %s", expense.pk, recipient.pk)
            continue
        details = {**context, "confirmation": confirmation, "status": expense.get_status_display()}
        subject = f"Homebase: expense {expense.expense_number} " + (
            "submitted successfully" if confirmation else "needs your approval")
        if not submitted:
            subject = f"Homebase: expense {expense.expense_number} {expense.get_status_display().lower()}"
        if settings.EMAIL_TEST_MODE:
            subject = "[TEST] " + subject
        try:
            template = "submission" if submitted else "decision"
            text = render_to_string(f"expenses/email/{template}.txt", details)
            html = render_to_string(f"expenses/email/{template}.html", details)
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[address],
            )
            message.attach_alternative(
                html, "text/html")
            message.send(using="transactional")
        except Exception:
            # The expense is already committed; never imply that submission
            # failed and encourage a duplicate submission after an SMTP error.
            logger.exception("Expense %s notification failed for user %s", expense.pk, recipient.pk)
