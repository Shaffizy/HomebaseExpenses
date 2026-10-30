from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.models import Role
from expenses.models import ExpenseStatus

class ExpenseAccessPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action == "create":
            return request.user.role in (Role.REQUESTER, Role.REVIEWER) and not request.user.is_staff
        return True

    def has_object_permission(self, request, view, obj):
        if view.action in ("update", "partial_update", "destroy"):
            return (request.user.role in (Role.REQUESTER, Role.REVIEWER) and not request.user.is_staff and obj.created_by_id == request.user.pk and obj.status in (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED) and obj.organization_id == request.user.organization_id)
        return True

class CategoryAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or (
            request.user.is_authenticated and request.user.is_active
            and request.user.role == Role.ADMIN and request.user.is_staff
        )
