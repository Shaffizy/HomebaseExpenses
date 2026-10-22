import logging
import smtplib
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .permissions import IsAdmin

logger = logging.getLogger(__name__)


def delivery_status():
    mailer = settings.MAILERS["transactional"]
    backend = mailer["BACKEND"]
    options = mailer.get("OPTIONS", {})
    reason = ""
    ready = False
    mode = "unsupported"
    if backend == "django.core.mail.backends.console.EmailBackend":
        mode, reason = "console", "Preview only. Messages print in the backend terminal; nothing reaches an inbox."
    elif backend == "django.core.mail.backends.locmem.EmailBackend":
        mode, reason = "test", "Automated testing only. No external email is sent."
    elif backend == "django.core.mail.backends.smtp.EmailBackend":
        mode = "smtp"
        if not options.get("host"):
            reason = "The application email server is not configured."
        elif not options.get("username") or not options.get("password"):
            reason = "The application's sender credentials are missing. Users do not need to connect their mailboxes."
        elif not (bool(options.get("use_tls")) ^ bool(options.get("use_ssl"))):
            reason = "Configure exactly one secure connection option: TLS or SSL."
        else:
            ready = True
    else:
        reason = "The email backend is not supported by this status check."
    try:
        address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        validate_email(address)
        if address.endswith("@localhost"):
            raise ValidationError("Local address")
    except (ValidationError, ValueError):
        ready = False
        if mode == "smtp":
            reason = "Set a valid sender address authorized by your email provider."
    return {"mode": mode, "configured": ready, "sender": settings.DEFAULT_FROM_EMAIL,
            "detail": reason or "Sender settings are configured. Send a test to check provider acceptance."}


class EmailTestThrottle(UserRateThrottle):
    scope = "application_email_test"
    rate = "5/hour"


class EmailDeliveryView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({**delivery_status(), "test_recipient": request.user.email}, headers={"Cache-Control": "no-store"})

    def get_throttles(self):
        return [EmailTestThrottle()] if self.request.method == "POST" else super().get_throttles()

    def post(self, request):
        status = delivery_status()
        if not status["configured"]:
            raise serializers.ValidationError({"detail": status["detail"]})
        try:
            validate_email(request.user.email)
        except ValidationError:
            raise serializers.ValidationError({"detail": "Your administrator account needs a valid email address before testing."}) from None
        try:
            count = EmailMessage(subject="Homebase Expenses - notification test",
                body="This is a Homebase application email test. Individual users do not need to connect a mailbox.",
                from_email=settings.DEFAULT_FROM_EMAIL, to=[request.user.email]).send(using="transactional")
            if count != 1:
                raise RuntimeError("No message accepted")
        except smtplib.SMTPAuthenticationError:
            raise serializers.ValidationError({"detail": "The provider rejected the application sender credentials. Update the SMTP password or provider SMTP key."}) from None
        except Exception as exc:
            logger.warning("Application email test failed for admin %s, error type %s", request.user.pk, type(exc).__name__)
            raise serializers.ValidationError({"detail": "The test could not be confirmed. Check the application's sender and email server settings before retrying."}) from None
        return Response({"detail": "The provider accepted the test email. Check your inbox and spam folder; inbox delivery is not yet confirmed."})
