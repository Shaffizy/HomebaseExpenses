"""Homebase expense workflow mail, delivered only after a committed transition."""

import logging
import ipaddress
from email.message import MIMEPart
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from accounts.models import Department, Role
from .models import ExpenseStatus

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _logo_bytes() -> bytes:
    candidates = [
        Path(settings.BASE_DIR).parent / "frontend" / "public" / "homebase-logo.png",
        Path(settings.BASE_DIR) / "expenses" / "static" / "expenses" / "homebase-logo.png",
    ]
    for path in candidates:
        if path.is_file():
            try:
                return path.read_bytes()
            except OSError:
                continue
    return b""


def _attach_company_logo(message: EmailMultiAlternatives) -> bool:
    data = _logo_bytes()
    if not data:
        return False
    part = MIMEPart()
    part.set_content(
        data,
        maintype="image",
        subtype="png",
        disposition="inline",
        filename="homebase-logo.png",
        cid="<homebase-logo>",
    )
    message.attach(part)
    return True


def public_expense_url(expense):
    base = settings.FRONTEND_URL.rstrip('/')
    try:
        URLValidator(schemes=["http", "https"])(base)
        parsed = urlsplit(base)
        host = (parsed.hostname or "").lower().rstrip('.')
        if parsed.username or parsed.password or parsed.query or parsed.fragment or not host:
            return ""
        if host == "localhost" or host.endswith(".localhost"):
            return ""
        try:
            address = ipaddress.ip_address(host)
            if address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast:
                return ""
        except ValueError:
            pass
        return f"{base}/expenses/{expense.pk}"
    except (ValidationError, ValueError):
        return ""



def notify_next_role(expense):
    if expense.status not in {
        ExpenseStatus.IN_REVIEW,
        ExpenseStatus.IN_FINCON_REVIEW,
        ExpenseStatus.SUBMITTED,
        ExpenseStatus.APPROVED,
        ExpenseStatus.RETURNED,
        ExpenseStatus.REJECTED,
    }:
        return
    requester = expense.created_by
    approver = expense.assigned_approver
    if (approver is None or not approver.is_active or approver.role != Role.APPROVER
            or approver.organization_id != expense.organization_id
            or requester.organization_id != expense.organization_id):
        logger.error("Invalid notification routing for expense %s", expense.pk)
        return
    reviewer = expense.assigned_reviewer
    in_dept_review = expense.status == ExpenseStatus.IN_REVIEW
    in_fincon_review = expense.status == ExpenseStatus.IN_FINCON_REVIEW
    in_review = in_dept_review or in_fincon_review
    recipient_owner = reviewer if in_review else approver
    if in_dept_review and (
        reviewer is None
        or not reviewer.is_active
        or reviewer.role != Role.REVIEWER
        or reviewer.organization_id != expense.organization_id
        or not reviewer.department
        or reviewer.department != expense.department
    ):
        logger.error("Invalid reviewer routing for expense %s", expense.pk)
        return
    if in_fincon_review and (
        reviewer is None
        or not reviewer.is_active
        or reviewer.role != Role.REVIEWER
        or reviewer.organization_id != expense.organization_id
        or reviewer.department != Department.FINCON
    ):
        logger.error("Invalid FinCon reviewer routing for expense %s", expense.pk)
        return
    stage = "FinCon review" if in_fincon_review else ("review" if in_dept_review else "approval")
    has_wht = bool(expense.wht_classification)
    net_val = expense.total - (expense.wht_amount or 0)
    context = {
        "number": expense.expense_number,
        "requester": requester.get_full_name() or requester.username,
        "approver": recipient_owner.name,
        "stage": stage,
        "category": expense.title or (expense.category.name if expense.category else "Untitled expense"),
        "department": expense.department,
        "branch": expense.branch,
        "total": f"{expense.total:,.2f}",
        "has_wht": has_wht,
        "wht_classification": expense.get_wht_classification_display() if has_wht else "",
        "wht_rate": f"{expense.wht_rate:.2f}" if has_wht else "",
        "wht_amount": f"{expense.wht_amount:,.2f}" if has_wht else "",
        "net_total": f"{net_val:,.2f}",
        "url": public_expense_url(expense),
        "has_logo": bool(_logo_bytes()),
        "test_mode": settings.EMAIL_TEST_MODE,
    }
    # Separate messages keep recipients private and allow one delivery to fail
    # without preventing the other recipient's notification.
    submitted = expense.status in (ExpenseStatus.IN_REVIEW, ExpenseStatus.IN_FINCON_REVIEW, ExpenseStatus.SUBMITTED)
    recipients = ((requester, True), (recipient_owner, False)) if submitted else ((requester, False),)
    for recipient, confirmation in recipients:
        address = recipient.email
        if not address:
            logger.warning("Missing notification email for expense %s user %s", expense.pk, recipient.pk)
            continue
        details = {**context, "confirmation": confirmation, "status": expense.get_status_display()}
        subject = f"Homebase: expense {expense.expense_number} " + (
            "submitted successfully" if confirmation else f"requires your {context['stage']}")
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
            _attach_company_logo(message)
            message.send(using="transactional")
        except Exception:
            # The expense is already committed; never imply that submission
            # failed and encourage a duplicate submission after an SMTP error.
            logger.exception("Expense %s notification failed for user %s", expense.pk, recipient.pk)
