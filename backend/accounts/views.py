from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.password_validation import password_changed
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.throttling import UserRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Organization
from .permissions import IsAdmin
from .serializers import (
    LoginSerializer,
    RegisterUserSerializer,
    UserAdminSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    PasswordAwareRefreshSerializer,
)


class LoginRateThrottle(SimpleRateThrottle):
    """Per-IP login throttle (5/minute)."""

    scope = "login"

    def get_cache_key(self, request, view):
        return f"throttle_login_{self.get_ident(request)}"

class PasswordChangeThrottle(UserRateThrottle):
    scope = "password_change"

class RefreshView(TokenRefreshView):
    serializer_class = PasswordAwareRefreshSerializer

class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeThrottle]

    def post(self, request):
        from .models import User
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            serializer = self.get_serializer(instance=user, data=request.data)
            serializer.is_valid(raise_exception=True)
            new_password = serializer.validated_data["new_password"]
            user.set_password(new_password)
            user.save(update_fields=["password"])
            password_changed(new_password, user)
        return Response({"detail": "Password changed. Please sign in again."})


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        from .models import User

        identifier = request.data.get("username", "")
        lookup = identifier
        if "@" in str(identifier):
            # Allow signing in with the email address instead of the username.
            matched = User.objects.filter(email__iexact=str(identifier)).first()
            if matched is not None:
                lookup = matched.username
                if hasattr(request.data, "_mutable"):
                    request.data._mutable = True
                request.data["username"] = lookup

        try:
            user = User.objects.get(username=lookup)
        except User.DoesNotExist:
            user = None

        if user is not None and user.locked_until and user.locked_until > timezone.now():
            remaining = int((user.locked_until - timezone.now()).total_seconds())
            return Response(
                {
                    "detail": f"Account temporarily locked. Try again in {remaining}s."
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            # TokenObtainPairView raises AuthenticationFailed for bad
            # credentials; record the attempt, then let dispatch convert it.
            if user is not None:
                user.register_failed_login()
            raise

        if response.status_code == 200 and user is not None:
            user.register_successful_login()

        return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


class OrganizationUsersView(generics.ListAPIView):
    """Users of a given organization, including their role/privileges.

    Only staff (admin) accounts may read this; the queryset is still org-scoped.
    """

    serializer_class = UserAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        # Always scoped to the caller's own organization: asking for another
        # org's user list yields an empty result rather than leaking members.
        organization = get_object_or_404(Organization, pk=self.kwargs["org_id"])
        if organization.id != self.request.user.organization_id:
            return organization.users.none()
        return organization.users.select_related("organization").order_by("username")


class RegisterUserView(generics.CreateAPIView):
    """Admin-only user registration (staff accounts only)."""

    serializer_class = RegisterUserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UpdateUserView(generics.UpdateAPIView):
    """Edit an existing user (admin only, same org)."""

    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return self.request.user.organization.users.all()


class DeleteUserView(generics.DestroyAPIView):
    """Deactivate/remove a user (admin only, same org)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return self.request.user.organization.users.exclude(
            id=self.request.user.id
        )

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=204)
