from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms

from .models import Organization, Role, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name",)



@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "organization",
        "is_staff",
        "is_active",
        "last_login",
    )
    list_filter = ("role", "organization", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = ("failed_login_attempts", "locked_until")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Org", {"fields": ("organization", "role")}),
        ("Security", {"fields": ("failed_login_attempts", "locked_until")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Org", {"fields": ("organization", "role")}),
    )
