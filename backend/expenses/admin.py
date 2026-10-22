from django.contrib import admin
from accounts.models import Role
from .models import Expense, ExpenseItem, ExpenseCategory

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    fields = ("name", "is_active")
    list_display = ("name", "is_active", "organization")
    def get_queryset(self, request):
        return super().get_queryset(request).filter(organization=request.user.organization)
    def save_model(self, request, obj, form, change):
        if not change:
            obj.organization = request.user.organization
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    def has_add_permission(self, request):
        return request.user.role == Role.ADMIN and super().has_add_permission(request)
    def has_change_permission(self, request, obj=None):
        return request.user.role == Role.ADMIN and super().has_change_permission(request, obj)
    def delete_model(self, request, obj):
        obj.is_active = False
        obj.save(update_fields=["is_active"])
    def delete_queryset(self, request, queryset):
        queryset.update(is_active=False)

class AuditOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(organization=request.user.organization) if self.model is Expense else queryset.filter(expense__organization=request.user.organization)

@admin.register(Expense)
class ExpenseAdmin(AuditOnlyAdmin):
    list_display = ("expense_number", "category", "department", "branch", "status", "total", "created_by")
    list_filter = ("status", "department", "branch")
    search_fields = ("expense_number", "category__name", "department")

@admin.register(ExpenseItem)
class ExpenseItemAdmin(AuditOnlyAdmin):
    list_display = ("expense", "description", "quantity", "unit_price", "line_total")
