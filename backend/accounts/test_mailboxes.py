import hashlib
import json
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.mailboxes import (MailboxError, begin_authorization, finish_authorization,
    check_connection, recipient_address, send_connected)
from accounts.models import Organization, User, Role, ConnectedMailbox, MailboxAuthorization

PASSWORD = "Homebase-Test-Password-43!"


@pytest.fixture
def person(db, settings):
    settings.EMAIL_PERSONAL_CONNECTIONS_ENABLED = True
    settings.EMAIL_TOKEN_KEY = Fernet.generate_key().decode()
    settings.GMAIL_CLIENT_ID = "test-client"
    settings.GMAIL_CLIENT_SECRET = "test-secret"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    cache.clear()
    org = Organization.objects.create(name="Homebase email tests")
    return User.objects.create_user(username="owner", email="owner@example.test", organization=org, role=Role.REQUESTER, password=PASSWORD)


def client(person):
    result = APIClient()
    result.force_authenticate(person)
    return result


def mailbox(person, settings):
    token = {"access_token": "ACCESS-SECRET", "refresh_token": "REFRESH-SECRET", "expires_at": time.time() + 3600, "token_type": "Bearer"}
    return ConnectedMailbox.objects.create(user=person, organization=person.organization, provider="gmail", email="verified@example.test",
        encrypted_token=Fernet(settings.EMAIL_TOKEN_KEY.encode()).encrypt(json.dumps(token).encode()).decode())


def state_for(person, email="new@example.test"):
    return parse_qs(urlparse(begin_authorization(person, "gmail", email)).query)["state"][0]


@pytest.mark.parametrize("method,path", [("get", ""), ("post", ""), ("delete", ""), ("post", "/callback"), ("post", "/check"), ("post", "/test")])
def test_requires_auth(person, method, path):
    assert getattr(APIClient(), method)("/api/auth/mailbox" + path).status_code == 401


@pytest.mark.parametrize("role", Role.values)
def test_all_roles_manage_own_connection(person, settings, role):
    person.role = role
    person.save()
    connection = mailbox(person, settings)
    result = client(person).get("/api/auth/mailbox")
    assert result.status_code == 200
    assert result.data["connection"]["email"] == connection.email
    assert "SECRET" not in json.dumps(result.data)
    assert "encrypted_token" not in result.data["connection"]


@pytest.mark.parametrize("email", ["not-an-email", "bad@@example.com", "person@example.test\r\nBcc: victim@example.test"])
def test_invalid_addresses_rejected(person, email):
    response = client(person).post("/api/auth/mailbox", {"provider": "gmail", "email": email, "current_password": PASSWORD}, format="json")
    assert response.status_code == 400
    assert not MailboxAuthorization.objects.exists()


def test_current_password_and_setup_required(person, settings):
    data = {"provider": "gmail", "email": "new@example.test", "current_password": "wrong"}
    assert client(person).post("/api/auth/mailbox", data, format="json").status_code == 400
    settings.GMAIL_CLIENT_ID = ""
    data["current_password"] = PASSWORD
    assert client(person).post("/api/auth/mailbox", data, format="json").status_code == 400


def test_authorization_uses_pkce_and_new_attempt_invalidates_old(person):
    first = state_for(person)
    url = begin_authorization(person, "gmail", "new@example.test")
    assert "code_challenge_method=S256" in url
    assert "accounts.google.com" == urlparse(url).hostname
    assert MailboxAuthorization.objects.count() == 1
    assert not MailboxAuthorization.objects.filter(state_hash=hashlib.sha256(first.encode()).hexdigest()).exists()


def mock_tokens():
    session = Mock()
    session.fetch_token.return_value = {"access_token": "ACCESS-SECRET", "refresh_token": "REFRESH-SECRET", "expires_at": time.time() + 3600,
        "scope": ["https://www.googleapis.com/auth/gmail.send"], "token_type": "Bearer"}
    return session


def test_verified_connect_encrypts_token_and_is_single_use(person, settings):
    state = state_for(person)
    with patch("accounts.mailboxes.OAuth2Session", return_value=mock_tokens()), patch("accounts.mailboxes.identity", return_value=("new@example.test", "")):
        finish_authorization(person, state, "provider-code")
        with pytest.raises(MailboxError):
            finish_authorization(person, state, "provider-code")
    connection = ConnectedMailbox.objects.get(user=person)
    assert "REFRESH-SECRET" not in connection.encrypted_token
    assert "REFRESH-SECRET" in Fernet(settings.EMAIL_TOKEN_KEY.encode()).decrypt(connection.encrypted_token.encode()).decode()
    assert recipient_address(person) == "new@example.test"
    person.refresh_from_db()
    assert person.email == "owner@example.test"


def test_wrong_mailbox_keeps_previous_connection(person, settings):
    old = mailbox(person, settings)
    state = state_for(person)
    with patch("accounts.mailboxes.OAuth2Session", return_value=mock_tokens()), patch("accounts.mailboxes.identity", return_value=("wrong@example.test", "")):
        with pytest.raises(MailboxError, match="different email"):
            finish_authorization(person, state, "code")
    old.refresh_from_db()
    assert old.email == "verified@example.test"


def test_other_user_cannot_consume_state_or_access_connection(person, settings):
    mailbox(person, settings)
    state = state_for(person)
    other_org = Organization.objects.create(name="Other")
    other = User.objects.create_user(username="other", organization=other_org, role=Role.REQUESTER)
    with pytest.raises(MailboxError):
        finish_authorization(other, state, "code")
    assert MailboxAuthorization.objects.filter(user=person).exists()
    assert client(other).get("/api/auth/mailbox").data["connection"] is None


def test_expired_state_rejected(person):
    state = state_for(person)
    MailboxAuthorization.objects.update(expires_at=timezone.now())
    with pytest.raises(MailboxError):
        finish_authorization(person, state, "code")


def test_missing_send_permission_rejected(person):
    state = state_for(person)
    session = mock_tokens()
    session.fetch_token.return_value["scope"] = []
    with patch("accounts.mailboxes.OAuth2Session", return_value=session):
        with pytest.raises(MailboxError, match="permission"):
            finish_authorization(person, state, "code")
    assert not ConnectedMailbox.objects.exists()


def test_check_failure_sets_reconnect_status(person, settings):
    connection = mailbox(person, settings)
    with patch("accounts.mailboxes.identity", side_effect=MailboxError("revoked")):
        assert not check_connection(person)
    connection.refresh_from_db()
    assert connection.needs_reconnect


def test_test_email_can_only_go_to_own_verified_address(person, settings):
    mailbox(person, settings)
    with patch("accounts.mailbox_views.send_connected") as send:
        result = client(person).post("/api/auth/mailbox/test", {"recipient": "victim@example.test", "subject": "Injected"}, format="json")
    assert result.status_code == 200
    assert send.call_args.args[1] == "verified@example.test"
    assert send.call_args.args[2] == "Homebase Expenses - connection test"


def test_disconnect_requires_password_and_preserves_other_accounts(person, settings):
    mailbox(person, settings)
    assert client(person).delete("/api/auth/mailbox", {"current_password": "wrong"}, format="json").status_code == 400
    assert ConnectedMailbox.objects.filter(user=person).exists()
    assert client(person).delete("/api/auth/mailbox", {"current_password": PASSWORD}, format="json").status_code == 204
    assert not ConnectedMailbox.objects.filter(user=person).exists()


def test_send_uses_connected_identity_not_login_email(person, settings):
    mailbox(person, settings)
    response = Mock(ok=True)
    with patch("accounts.mailboxes.requests.post", return_value=response) as post:
        send_connected(person, "approver@example.test", "Homebase test", "Body")
    raw = post.call_args.kwargs["json"]["raw"]
    import base64
    message = base64.urlsafe_b64decode(raw).decode()
    assert "From: verified@example.test" in message
    assert "To: approver@example.test" in message
    assert "owner@example.test" not in message


def test_mutations_are_throttled(person):
    for _ in range(10):
        client(person).post("/api/auth/mailbox/check")
    assert client(person).post("/api/auth/mailbox/check").status_code == 429


def test_zoho_uses_only_confirmed_primary_mailbox(person, settings):
    from accounts.mailboxes import identity
    response = Mock()
    response.json.return_value = {"data": [{"type": "ZOHO_ACCOUNT", "enabled": True,
        "mailboxStatus": "enabled", "accountId": "12345", "emailAddress": [
            {"isPrimary": True, "isConfirmed": True, "mailId": "person@company.test"}]}]}
    with patch("accounts.mailboxes.requests.get", return_value=response):
        assert identity("zoho", {"access_token": "token"}) == ("person@company.test", "12345")
    response.json.return_value["data"][0]["emailAddress"][0]["isConfirmed"] = False
    with patch("accounts.mailboxes.requests.get", return_value=response):
        with pytest.raises(MailboxError):
            identity("zoho", {"access_token": "token"})


def test_zoho_send_uses_own_account_and_checked_response(person, settings):
    connection = mailbox(person, settings)
    connection.provider, connection.account_id = "zoho", "12345"
    connection.save()
    response = Mock(ok=True)
    response.json.return_value = {"status": {"code": 200}}
    with patch("accounts.mailboxes.requests.post", return_value=response) as post:
        send_connected(person, "approver@example.test", "Expense", "Body")
    assert post.call_args.args[0] == "https://mail.zoho.com/api/accounts/12345/messages"
    assert post.call_args.kwargs["json"]["fromAddress"] == "verified@example.test"
    response.json.return_value = {"status": {"code": 403}}
    with patch("accounts.mailboxes.requests.post", return_value=response), pytest.raises(MailboxError):
        send_connected(person, "approver@example.test", "Expense", "Body")


def test_invalid_zoho_host_cannot_be_injected(person, settings):
    from accounts.mailboxes import provider_config
    settings.ZOHO_REGION = "com/../../evil.example"
    with pytest.raises(MailboxError):
        provider_config("zoho")
