from django.urls import path
from .signature_views import SignatureView
from .email_delivery_views import EmailDeliveryView
from .mailbox_views import MailboxView, MailboxCallbackView, MailboxCheckView, MailboxTestView
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    DeleteUserView,
    LoginView,
    OrganizationUsersView,
    RegisterUserView,
    UpdateUserView,
    me,
    ChangePasswordView,
    RefreshView,
)

urlpatterns = [
    path("auth/email-delivery", EmailDeliveryView.as_view(), name="email-delivery"),
    path("auth/mailbox", MailboxView.as_view()),
    path("auth/mailbox/callback", MailboxCallbackView.as_view()),
    path("auth/mailbox/check", MailboxCheckView.as_view()),
    path("auth/mailbox/test", MailboxTestView.as_view()),
    path("auth/signature", SignatureView.as_view(), name="signature"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/refresh", RefreshView.as_view(), name="token_refresh"),
    path("auth/change-password", ChangePasswordView.as_view(), name="change_password"),
    path("auth/me", me, name="me"),
    path("auth/register", RegisterUserView.as_view(), name="register"),
    path(
        "organizations/<int:org_id>/users/<int:pk>/",
        UpdateUserView.as_view(),
        name="organization-user-update",
    ),
    path(
        "organizations/<int:org_id>/users/<int:pk>/delete/",
        DeleteUserView.as_view(),
        name="organization-user-delete",
    ),
    path(
        "organizations/<int:org_id>/users/",
        OrganizationUsersView.as_view(),
        name="organization-users",
    ),
]
