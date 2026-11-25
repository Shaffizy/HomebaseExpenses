from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from accounts.models import Department, Role, User
from expenses.models import Expense, ExpenseStatus, Comment
from .notifications import notify_next_role

CLOSEABLE_STATUSES = (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED, ExpenseStatus.REJECTED)

class TransitionError(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

RULES = {
    "submit": {role: {ExpenseStatus.DRAFT, ExpenseStatus.RETURNED} for role in (Role.REQUESTER, Role.REVIEWER)},
    "review": {Role.REVIEWER: {ExpenseStatus.IN_REVIEW, ExpenseStatus.IN_FINCON_REVIEW}},
    "approve": {Role.APPROVER: {ExpenseStatus.SUBMITTED}},
    "return": {
        Role.APPROVER: {ExpenseStatus.SUBMITTED},
        Role.REVIEWER: {ExpenseStatus.IN_REVIEW, ExpenseStatus.IN_FINCON_REVIEW},
    },
    "reject": {
        Role.APPROVER: {ExpenseStatus.SUBMITTED},
        Role.REVIEWER: {ExpenseStatus.IN_REVIEW},
    },
}
TARGET_STATUS = {
    "review": ExpenseStatus.SUBMITTED,
    "submit": ExpenseStatus.IN_REVIEW,
    "approve": ExpenseStatus.APPROVED,
    "return": ExpenseStatus.RETURNED,
    "reject": ExpenseStatus.REJECTED,
}
REQUIRES_COMMENT = {"return", "reject"}

def current_stage_record(expense):
    previous = expense.history.exclude(status=expense.status).order_by("-history_id").first()
    records = expense.history.filter(status=expense.status)
    if previous:
        records = records.filter(history_id__gt=previous.history_id)
    return records.order_by("history_id").first()

def current_stage_comment(expense, user):
    entered = current_stage_record(expense)
    if entered is None:
        return None
    return expense.comments.filter(author=user, stage_history_id=entered.history_id).exclude(text="").order_by("-id").first()

def _resolve_approver(expense):
    return User.objects.filter(organization_id=expense.organization_id, role=Role.APPROVER, is_active=True).first()

def _resolve_fincon_reviewer(expense):
    return User.objects.filter(
        organization_id=expense.organization_id,
        role=Role.REVIEWER,
        is_active=True,
        department=Department.FINCON,
    ).order_by("pk").first()

def calculate_wht_amounts(total: Decimal, wht_classification: str) -> tuple[Decimal, Decimal, Decimal]:
    rate = Expense.WHT_RATES[wht_classification]
    wht_amount = (total * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net_total = (total - wht_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return rate, wht_amount, net_total

@transaction.atomic
def transition(expense, user, action, comment=None, wht_classification=None):
    expense = Expense.objects.select_for_update().select_related("organization", "created_by").get(pk=expense.pk)
    if expense.organization_id != user.organization_id:
        raise TransitionError("Not found.", 404)
    if not user.is_active or user.role == Role.ADMIN or user.is_staff:
        raise TransitionError("Administrators cannot perform expense workflow actions.", 403)
    if action not in RULES:
        raise TransitionError("Unknown action.", 400)
    allowed = RULES[action].get(user.role)
    if allowed is None:
        raise TransitionError("Your role cannot perform this action.", 403)
    if expense.status not in allowed:
        raise TransitionError(f"Cannot {action} an expense in {expense.status}.", 409)
    if action == "submit" and expense.created_by_id != user.pk:
        raise TransitionError("Only the requester who created this expense can submit it.", 403)
    approver = _resolve_approver(expense)
    if user.role == Role.APPROVER and (approver is None or approver.pk != user.pk):
        raise TransitionError("Only the organization's active approver can act.", 403)
    if action == "submit":
        if not expense.title or not expense.title.strip():
            raise TransitionError("Select a category and save the expense before submitting.", 400)
        if expense.department not in Expense.Department.values or expense.branch not in Expense.Branch.values:
            raise TransitionError("Select a valid department and branch before submitting.", 400)
        if user.department not in Expense.Department.values:
            raise TransitionError("Ask your administrator to assign your department before submitting.", 409)
        if expense.department != user.department:
            raise TransitionError("You can only submit expenses for your assigned department. Edit the draft before submitting.", 403)
        if not expense.items.exists():
            raise TransitionError("Add at least one item.", 400)
        if approver is None:
            raise TransitionError("No active approver is configured.", 409)
        expense.assigned_approver = approver
    prior_status = expense.status
    is_own_fincon_wht_review = (
        action == "review"
        and prior_status == ExpenseStatus.IN_FINCON_REVIEW
        and user.role == Role.REVIEWER
        and user.department == Department.FINCON
        and expense.assigned_reviewer_id == user.pk
    )
    if action != "submit" and expense.created_by_id == user.pk and not is_own_fincon_wht_review:
        raise TransitionError("You cannot review or approve your own expense.", 403)
    if action != "submit" and user.role == Role.REVIEWER and expense.assigned_reviewer_id != user.pk:
        raise TransitionError("Only the assigned reviewer can act.", 403)
    if action == "reject" and user.role == Role.REVIEWER and user.department == Department.FINCON:
        raise TransitionError("FinCon reviewers can only return expenses, not reject them.", 403)
    if action != "submit" and user.role == Role.REVIEWER:
        if prior_status == ExpenseStatus.IN_REVIEW and (not user.department or user.department != expense.department):
            raise TransitionError("You can only review expenses in your assigned department.", 403)
        if prior_status == ExpenseStatus.IN_FINCON_REVIEW and user.department != Department.FINCON:
            raise TransitionError("Only an active FinCon reviewer can complete the FinCon WHT review.", 403)
    reviewer = None
    next_status = TARGET_STATUS[action]
    if action == "submit":
        if user.role == Role.REQUESTER and user.department != Department.FINCON:
            reviewer = User.objects.filter(
                organization_id=expense.organization_id,
                role=Role.REVIEWER,
                is_active=True,
                department=user.department,
            ).exclude(pk=expense.created_by_id).order_by("pk").first()
            if reviewer is None:
                raise TransitionError("No active reviewer is configured for your department.", 409)
            next_status = ExpenseStatus.IN_REVIEW
        else:
            reviewer = _resolve_fincon_reviewer(expense)
            if reviewer is None:
                raise TransitionError("No active FinCon reviewer is configured.", 409)
            next_status = ExpenseStatus.IN_FINCON_REVIEW
    reused = None
    if action in REQUIRES_COMMENT:
        if comment is not None and not isinstance(comment, str):
            raise TransitionError("Comment must be text.", 400)
        if not comment or not comment.strip():
            reused = current_stage_comment(expense, user)
            if reused is None or not reused.text.strip():
                raise TransitionError("A comment is required.", 400)
            comment = reused.text
    if action == "review":
        if approver is None:
            raise TransitionError("No active approver is configured.", 409)
        if prior_status == ExpenseStatus.IN_REVIEW:
            fincon_reviewer = _resolve_fincon_reviewer(expense)
            if fincon_reviewer is None:
                raise TransitionError("No active FinCon reviewer is configured.", 409)
            expense.reviewed_by = user
            expense.reviewed_at = timezone.now()
            expense.assigned_reviewer = fincon_reviewer
            expense.assigned_approver = approver
            next_status = ExpenseStatus.IN_FINCON_REVIEW
        elif prior_status == ExpenseStatus.IN_FINCON_REVIEW:
            if not isinstance(wht_classification, str) or wht_classification not in Expense.WhtClassification.values:
                raise TransitionError("Select a valid withholding tax (WHT) classification before forwarding for approval.", 400)
            rate, wht_amount, net_total = calculate_wht_amounts(expense.total, wht_classification)
            expense.wht_classification = wht_classification
            expense.wht_rate = rate
            expense.wht_amount = wht_amount
            expense.net_total = net_total
            expense.fincon_reviewed_by = user
            expense.fincon_reviewed_at = timezone.now()
            expense.assigned_approver = approver
            next_status = ExpenseStatus.SUBMITTED
    expense._actor = user
    expense.status = next_status
    if action == "submit":
        expense.assigned_reviewer = reviewer
        expense.reviewed_by = None
        expense.reviewed_at = None
        expense.fincon_reviewed_by = None
        expense.fincon_reviewed_at = None
        expense.wht_classification = ""
        expense.wht_rate = Decimal("0.00")
        expense.wht_amount = Decimal("0.00")
        expense.net_total = expense.total
    if action == "approve":
        signer = User.objects.select_for_update().get(pk=user.pk)
        if not signer.is_active or signer.role != Role.APPROVER or signer.is_staff:
            raise TransitionError("Only the active approver can approve.", 403)
        expense.approved_by = user
        expense.approved_at = timezone.now()
        expense.approved_signature_data = signer.signature_data
    expense.save(update_fields=[
        "status",
        "updated_at",
        "assigned_reviewer",
        "reviewed_by",
        "reviewed_at",
        "fincon_reviewed_by",
        "fincon_reviewed_at",
        "wht_classification",
        "wht_rate",
        "wht_amount",
        "net_total",
        "assigned_approver",
        "approved_by",
        "approved_at",
        "approved_signature_data",
    ])
    if action in REQUIRES_COMMENT and reused is None:
        stage = current_stage_record(expense)
        Comment.objects.create(expense=expense, author=user, text=comment.strip(), stage_history_id=stage.history_id)
    transaction.on_commit(lambda: notify_next_role(expense))
    return expense

@transaction.atomic
def close_expense(expense, user):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.organization_id != user.organization_id:
        raise TransitionError("Not found.", 404)
    if user.role not in (Role.REQUESTER, Role.REVIEWER) or user.is_staff or expense.created_by_id != user.pk:
        raise TransitionError("Only the expense's requester can close it.", 403)
    if expense.status not in CLOSEABLE_STATUSES:
        raise TransitionError("Cannot close this expense.", 409)
    expense._actor = user
    expense.status = ExpenseStatus.CLOSED
    expense.save(update_fields=["status", "updated_at"])
    return expense

def can_comment(user, expense):
    if not user.is_active or user.is_staff or expense.organization_id != user.organization_id:
        return False
    if expense.created_by_id == user.pk:
        return user.role in (Role.REQUESTER, Role.REVIEWER) and expense.status == ExpenseStatus.RETURNED
    if user.role == Role.REVIEWER:
        if expense.status == ExpenseStatus.IN_REVIEW:
            return bool(user.department) and user.department == expense.department and expense.assigned_reviewer_id == user.pk
        if expense.status == ExpenseStatus.IN_FINCON_REVIEW:
            return user.department == Department.FINCON and expense.assigned_reviewer_id == user.pk
        return False
    if user.role == Role.APPROVER:
        approver = _resolve_approver(expense)
        return approver is not None and approver.pk == user.pk and expense.status == ExpenseStatus.SUBMITTED
    return False
