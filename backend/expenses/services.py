from django.db import transaction
from django.utils import timezone
from accounts.models import Role, User
from expenses.models import Expense, ExpenseStatus, Comment
from .notifications import notify_next_role

CLOSEABLE_STATUSES = (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED, ExpenseStatus.REJECTED)

class TransitionError(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

RULES = {
    "submit": {Role.REQUESTER: {ExpenseStatus.DRAFT, ExpenseStatus.RETURNED}},
    "approve": {Role.APPROVER: {ExpenseStatus.SUBMITTED}},
    "return": {Role.APPROVER: {ExpenseStatus.SUBMITTED}},
    "reject": {Role.APPROVER: {ExpenseStatus.SUBMITTED}},
}
TARGET_STATUS = {"submit": ExpenseStatus.SUBMITTED, "approve": ExpenseStatus.APPROVED, "return": ExpenseStatus.RETURNED, "reject": ExpenseStatus.REJECTED}
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

@transaction.atomic
def transition(expense, user, action, comment=None):
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
    if user.role == Role.REQUESTER and expense.created_by_id != user.pk:
        raise TransitionError("Only the requester who created this expense can submit it.", 403)
    approver = _resolve_approver(expense)
    if user.role == Role.APPROVER and (approver is None or approver.pk != user.pk):
        raise TransitionError("Only the organization's active approver can act.", 403)
    if action == "submit":
        if not expense.title or not expense.title.strip():
            raise TransitionError("Enter an expense name before submitting.", 400)
        if expense.department not in Expense.Department.values or expense.branch not in Expense.Branch.values:
            raise TransitionError("Select a valid department and branch before submitting.", 400)
        if not expense.items.exists():
            raise TransitionError("Add at least one item.", 400)
        if approver is None:
            raise TransitionError("No active approver is configured.", 409)
        expense.assigned_approver = approver
    reused = None
    if action in REQUIRES_COMMENT:
        if comment is not None and not isinstance(comment, str):
            raise TransitionError("Comment must be text.", 400)
        if not comment or not comment.strip():
            reused = current_stage_comment(expense, user)
            if reused is None or not reused.text.strip():
                raise TransitionError("A comment is required.", 400)
            comment = reused.text
    expense._actor = user
    expense.status = TARGET_STATUS[action]
    if action == "approve":
        signer = User.objects.select_for_update().get(pk=user.pk)
        if not signer.is_active or signer.role != Role.APPROVER or signer.is_staff:
            raise TransitionError("Only the active approver can approve.", 403)
        expense.approved_by = user
        expense.approved_at = timezone.now()
        expense.approved_signature_data = signer.signature_data
    expense.save(update_fields=["status", "updated_at", "assigned_approver", "approved_by", "approved_at", "approved_signature_data"])
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
    if user.role != Role.REQUESTER or user.is_staff or expense.created_by_id != user.pk:
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
    if user.role == Role.REQUESTER:
        return expense.created_by_id == user.pk and expense.status == ExpenseStatus.RETURNED
    if user.role == Role.APPROVER:
        approver = _resolve_approver(expense)
        return approver is not None and approver.pk == user.pk and expense.status == ExpenseStatus.SUBMITTED
    return False
