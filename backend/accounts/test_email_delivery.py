import json
import smtplib
from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import Organization, User, Role


@pytest.fixture
def admin(db, settings):
    settings.MAILERS = {"transactional": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend", "OPTIONS": {
        "host": "smtp.example.test", "port": 587, "username": "app-sender", "password": "PRIVATE-SMTP-KEY", "use_tls": True,
    }}}
    settings.DEFAULT_FROM_EMAIL = "Homebase <notifications@example.test>"
    settings.EMAIL_PERSONAL_CONNECTIONS_ENABLED = False
    cache.clear()
    org = Organization.objects.create(name="Homebase mail delivery")
    return User.objects.create(username="admin", email="admin@example.test", organization=org, role=Role.ADMIN)


def client(user=None):
    result = APIClient()
    if user:
        result.force_authenticate(user)
    return result


def test_email_delivery_requires_auth(admin):
    assert client().get("/api/auth/email-delivery").status_code == 401
    assert client().post("/api/auth/email-delivery").status_code == 401


@pytest.mark.parametrize("role", [Role.REQUESTER, Role.APPROVER])
def test_only_admin_can_inspect_or_test_sender(admin, role):
    user = User.objects.create(username=role, organization=admin.organization, role=role)
    assert client(user).get("/api/auth/email-delivery").status_code == 403
    assert client(user).post("/api/auth/email-delivery").status_code == 403


def test_status_never_exposes_sender_credentials(admin):
    response = client(admin).get("/api/auth/email-delivery")
    assert response.status_code == 200
    assert response.data["configured"]
    assert response.data["test_recipient"] == admin.email
    assert "PRIVATE-SMTP-KEY" not in json.dumps(response.data)
    assert "app-sender" not in json.dumps(response.data)


def test_missing_credentials_prevents_fake_success(admin, settings):
    settings.MAILERS["transactional"]["OPTIONS"]["password"] = ""
    assert not client(admin).get("/api/auth/email-delivery").data["configured"]
    with patch("accounts.email_delivery_views.EmailMessage.send") as send:
        assert client(admin).post("/api/auth/email-delivery").status_code == 400
    send.assert_not_called()


def test_console_mode_never_claims_inbox_delivery(admin, settings):
    settings.MAILERS = {"transactional": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
    response = client(admin).get("/api/auth/email-delivery")
    assert response.data["mode"] == "console"
    assert not response.data["configured"]
    assert client(admin).post("/api/auth/email-delivery").status_code == 400


def test_test_recipient_is_always_the_current_admin(admin):
    with patch("accounts.email_delivery_views.EmailMessage") as message:
        message.return_value.send.return_value = 1
        response = client(admin).post("/api/auth/email-delivery", {"to": "victim@example.test", "subject": "Arbitrary"}, format="json")
    assert response.status_code == 200
    assert message.call_args.kwargs["to"] == [admin.email]
    assert message.call_args.kwargs["subject"] == "Homebase Expenses - notification test"
    assert message.call_args.kwargs["from_email"] == "Homebase <notifications@example.test>"
    assert "inbox delivery is not yet confirmed" in response.data["detail"]


def test_smtp_failure_is_reported_without_leaking_secrets(admin):
    with patch("accounts.email_delivery_views.EmailMessage.send", side_effect=smtplib.SMTPAuthenticationError(535, b"PRIVATE-SMTP-KEY")):
        response = client(admin).post("/api/auth/email-delivery")
    assert response.status_code == 400
    assert "rejected" in response.data["detail"]
    assert "PRIVATE-SMTP-KEY" not in json.dumps(response.data)


def test_mail_tests_are_rate_limited(admin):
    with patch("accounts.email_delivery_views.EmailMessage.send", return_value=1):
        for _ in range(5):
            assert client(admin).post("/api/auth/email-delivery").status_code == 200
        assert client(admin).post("/api/auth/email-delivery").status_code == 429


@pytest.mark.parametrize("method,path", [("get", ""), ("post", ""), ("delete", ""), ("post", "/callback"), ("post", "/check"), ("post", "/test")])
def test_personal_mailbox_routes_are_retired(admin, method, path):
    assert getattr(client(admin), method)("/api/auth/mailbox" + path).status_code == 410
