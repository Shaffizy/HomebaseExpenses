from rest_framework.permissions import BasePermission
from .models import Role

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role == Role.ADMIN and request.user.is_staff)
