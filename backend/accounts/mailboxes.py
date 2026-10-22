"""Per-user OAuth mailboxes. Passwords and mailbox contents are never requested."""

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import timedelta
from email.message import EmailMessage

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.utils import timezone
from requests_oauthlib import OAuth2Session

from .models import ConnectedMailbox, MailboxAuthorization, User

logger = logging.getLogger(__name__)


class MailboxError(Exception):
    pass


def cipher():
    try:
        return Fernet(settings.EMAIL_TOKEN_KEY.encode())
    except (ValueError, TypeError):
        raise MailboxError("Email connection encryption is not configured. Contact your administrator.") from None


def provider_config(provider):
    if provider == "gmail":
        return {
            "client_id": settings.GMAIL_CLIENT_ID, "secret": settings.GMAIL_CLIENT_SECRET,
            "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",
            "scope": ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/userinfo.email"],
        }
    if provider == "zoho":
        region = settings.ZOHO_REGION
        if region not in {"com", "eu", "in", "com.au", "jp", "ca", "sa"}:
            raise MailboxError("Zoho's data center is not configured.")
        return {
            "client_id": settings.ZOHO_CLIENT_ID, "secret": settings.ZOHO_CLIENT_SECRET,
            "authorize": f"https://accounts.zoho.{region}/oauth/v2/auth",
            "token": f"https://accounts.zoho.{region}/oauth/v2/token",
            "api": f"https://mail.zoho.{region}/api",
            "scope": ["ZohoMail.accounts.READ", "ZohoMail.messages.CREATE"],
        }
    raise MailboxError("Choose Gmail or Zoho.")


def provider_ready(provider):
    try:
        config = provider_config(provider)
        cipher()
        return bool(config["client_id"] and config["secret"])
    except MailboxError:
        return False


def begin_authorization(user, provider, email):
    if not provider_ready(provider):
        raise MailboxError("This provider needs one-time application setup by your administrator.")
    config = provider_config(provider)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    session = OAuth2Session(config["client_id"], redirect_uri=settings.EMAIL_OAUTH_REDIRECT_URI, state=state,
                            scope=config["scope"] if provider == "gmail" else ",".join(config["scope"]))
    options = {"access_type": "offline", "prompt": "consent"}
    if provider == "gmail":
        options.update(login_hint=email, code_challenge_method="S256", code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("="))
    url, _ = session.authorization_url(config["authorize"], **options)
    with transaction.atomic():
        # A new attempt invalidates old tabs; no reusable states are retained.
        User.objects.select_for_update().get(pk=user.pk)
        MailboxAuthorization.objects.filter(user=user).delete()
        MailboxAuthorization.objects.create(user=user, provider=provider, expected_email=email.lower(),
            state_hash=hashlib.sha256(state.encode()).hexdigest(), verifier=verifier,
            expires_at=timezone.now() + timedelta(minutes=10))
    return url


def identity(provider, token):
    if provider == "gmail":
        result = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": "Bearer " + token["access_token"]}, timeout=15)
        result.raise_for_status()
        profile = result.json()
        if not profile.get("verified_email"):
            raise MailboxError("Google has not verified this email address.")
        return profile["email"].lower(), ""
    config = provider_config(provider)
    result = requests.get(config["api"] + "/accounts", headers={"Authorization": "Zoho-oauthtoken " + token["access_token"]}, timeout=15)
    result.raise_for_status()
    for account in result.json().get("data", []):
        if account.get("type") == "ZOHO_ACCOUNT" and account.get("enabled") and account.get("mailboxStatus") == "enabled":
            for address in account.get("emailAddress", []):
                if address.get("isPrimary") and address.get("isConfirmed"):
                    return address["mailId"].lower(), str(account["accountId"])
    raise MailboxError("No verified, enabled Zoho mailbox was found in this data center.")


def finish_authorization(user, state, code):
    # Consume the attempt before contacting the provider, even on failure.
    with transaction.atomic():
        attempt = MailboxAuthorization.objects.select_for_update().filter(user=user,
            state_hash=hashlib.sha256(state.encode()).hexdigest(), expires_at__gt=timezone.now()).first()
        if attempt is None:
            raise MailboxError("This connection link expired or is invalid. Start again.")
        attempt.delete()
    config = provider_config(attempt.provider)
    try:
        session = OAuth2Session(config["client_id"], redirect_uri=settings.EMAIL_OAUTH_REDIRECT_URI)
        options = {"code_verifier": attempt.verifier} if attempt.provider == "gmail" else {}
        token = session.fetch_token(config["token"], code=code, client_secret=config["secret"],
            include_client_id=True, timeout=15, **options)
        granted = token.get("scope", [])
        if isinstance(granted, str):
            granted = granted.replace(",", " ").split()
        required = config["scope"][0 if attempt.provider == "gmail" else 1]
        if required not in granted:
            raise MailboxError("Sending permission was not granted. Connect again and select the permission to send email on your behalf.")
        email, account_id = identity(attempt.provider, token)
        validate_email(email)
        if email.casefold() != attempt.expected_email.casefold():
            raise MailboxError("You signed into a different email address. Check the address and try again.")
        if not token.get("refresh_token"):
            raise MailboxError("Offline access was not granted. Reconnect and approve access.")
        encrypted = cipher().encrypt(json.dumps(dict(token)).encode()).decode()
        with transaction.atomic():
            current = User.objects.select_for_update().get(pk=user.pk, is_active=True, organization_id=user.organization_id)
            ConnectedMailbox.objects.update_or_create(user=current, defaults={"organization_id": current.organization_id,
                "provider": attempt.provider, "email": email, "account_id": account_id,
                "encrypted_token": encrypted, "needs_reconnect": False, "checked_at": timezone.now()})
    except MailboxError as exc:
        # These are our fixed validation messages, never provider payloads,
        # authorization codes, tokens or account passwords.
        logger.warning("Mailbox connection rejected for user %s (%s): %s", user.pk, attempt.provider, exc)
        raise
    except IntegrityError:
        raise MailboxError("This mailbox is already connected to another account in your organization.") from None
    except Exception as exc:
        logger.warning("Mailbox provider connection failed for user %s (%s), error type %s", user.pk, attempt.provider, type(exc).__name__)
        raise MailboxError("The provider could not verify this connection. Check your account and try again.") from None


def access_token(connection):
    try:
        token = json.loads(cipher().decrypt(connection.encrypted_token.encode()))
        if token.get("expires_at", 0) <= time.time() + 60:
            config = provider_config(connection.provider)
            refreshed = OAuth2Session(config["client_id"]).refresh_token(config["token"],
                refresh_token=token["refresh_token"], client_id=config["client_id"], client_secret=config["secret"], timeout=15)
            refreshed.setdefault("refresh_token", token["refresh_token"])
            token = dict(refreshed)
            connection.encrypted_token = cipher().encrypt(json.dumps(token).encode()).decode()
            connection.save(update_fields=["encrypted_token", "updated_at"])
        return token
    except (InvalidToken, ValueError, KeyError):
        connection.needs_reconnect = True
        connection.save(update_fields=["needs_reconnect"])
        raise MailboxError("Reconnect your mailbox to restore access.") from None
    except Exception:
        raise MailboxError("Your provider could not refresh access. Try checking the connection again.") from None


@transaction.atomic
def check_connection(user):
    connection = own_connection(user, lock=True)
    try:
        email, _ = identity(connection.provider, access_token(connection))
        if email.casefold() != connection.email.casefold():
            raise MailboxError("Mailbox identity changed. Reconnect your mailbox.")
        connection.needs_reconnect = False
        connection.checked_at = timezone.now()
        connection.save(update_fields=["checked_at", "needs_reconnect"])
    except Exception:
        # Return outside the transaction so the reconnect marker is committed.
        connection.needs_reconnect = True
        connection.save(update_fields=["needs_reconnect"])
        return False
    return True


def own_connection(user, lock=False):
    query = ConnectedMailbox.objects.select_for_update() if lock else ConnectedMailbox.objects
    connection = query.filter(user=user, organization_id=user.organization_id).first()
    if connection is None:
        raise MailboxError("Connect your mailbox in Settings first.")
    return connection


@transaction.atomic
def send_connected(user, recipient, subject, text, html=None):
    validate_email(recipient)
    connection = own_connection(user, lock=True)
    if not user.is_active or connection.needs_reconnect:
        raise MailboxError("Reconnect your mailbox in Settings before sending.")
    token = access_token(connection)
    if connection.provider == "gmail":
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = connection.email, recipient, subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")
        response = requests.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": "Bearer " + token["access_token"]},
            json={"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}, timeout=15)
    else:
        response = requests.post(provider_config("zoho")["api"] + f"/accounts/{connection.account_id}/messages",
            headers={"Authorization": "Zoho-oauthtoken " + token["access_token"]},
            json={"fromAddress": connection.email, "toAddress": recipient, "subject": subject,
                  "content": html or text, "mailFormat": "html" if html else "plaintext"}, timeout=15)
    if not response.ok or (connection.provider == "zoho" and response.json().get("status", {}).get("code") != 200):
        raise MailboxError("The provider did not accept this email. Check your connection and sending permission.")


def recipient_address(user):
    mailbox = ConnectedMailbox.objects.filter(user=user, organization_id=user.organization_id).first()
    return mailbox.email if mailbox else user.email
