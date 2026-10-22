import hashlib
from django.conf import settings
from rest_framework.exceptions import APIException

from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .mailboxes import (MailboxError, begin_authorization, check_connection,
    finish_authorization, provider_ready, send_connected)
from .models import ConnectedMailbox, MailboxAuthorization, User


class MailboxThrottle(UserRateThrottle):
    scope = "mailbox"
    rate = "10/hour"


class StartSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["gmail", "zoho"])
    email = serializers.EmailField(max_length=254)
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)


class CallbackSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=4096, required=False)
    error = serializers.CharField(max_length=200, required=False)


def connection_status(user):
    mailbox = ConnectedMailbox.objects.filter(user=user, organization_id=user.organization_id).first()
    return {
        "registered_email": user.email,
        "providers": {name: provider_ready(name) for name in ("gmail", "zoho")},
        "connection": None if mailbox is None else {
            "email": mailbox.email, "provider": mailbox.provider,
            "status": "reconnect_required" if mailbox.needs_reconnect else "connected",
            "checked_at": mailbox.checked_at,
        },
    }


class MailboxRetired(APIException):
    status_code = 410
    default_detail = "Personal email connections are no longer needed. Homebase uses one application sender."


class PersonalMailboxView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not settings.EMAIL_PERSONAL_CONNECTIONS_ENABLED:
            raise MailboxRetired()


class MailboxView(PersonalMailboxView):
    def get_throttles(self):
        return [MailboxThrottle()] if self.request.method != "GET" else super().get_throttles()

    def get(self, request):
        return Response(connection_status(request.user), headers={"Cache-Control": "no-store"})

    def post(self, request):
        serializer = StartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.check_password(data["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        try:
            return Response({"authorization_url": begin_authorization(request.user, data["provider"], data["email"])})
        except MailboxError as exc:
            raise serializers.ValidationError({"detail": str(exc)})

    @transaction.atomic
    def delete(self, request):
        password = request.data.get("current_password")
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not isinstance(password, str) or not user.check_password(password):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        ConnectedMailbox.objects.filter(user=user, organization_id=user.organization_id).delete()
        MailboxAuthorization.objects.filter(user=user).delete()
        return Response(status=204)


class MailboxCallbackView(PersonalMailboxView):
    throttle_classes = [MailboxThrottle]

    def post(self, request):
        serializer = CallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get("error") or not data.get("code"):
            MailboxAuthorization.objects.filter(user=request.user,
                state_hash=hashlib.sha256(data["state"].encode()).hexdigest()).delete()
            raise serializers.ValidationError({"detail": "Email connection was cancelled. Your existing mailbox was not changed."})
        try:
            finish_authorization(request.user, data["state"], data["code"])
        except MailboxError as exc:
            raise serializers.ValidationError({"detail": str(exc)})
        return Response(connection_status(request.user))


class MailboxCheckView(PersonalMailboxView):
    throttle_classes = [MailboxThrottle]

    def post(self, request):
        try:
            success = check_connection(request.user)
        except MailboxError as exc:
            raise serializers.ValidationError({"detail": str(exc)})
        if not success:
            raise serializers.ValidationError({"detail": "The provider could not verify access. Try again or reconnect your mailbox."})
        return Response(connection_status(request.user))


class MailboxTestView(PersonalMailboxView):
    throttle_classes = [MailboxThrottle]

    def post(self, request):
        mailbox = ConnectedMailbox.objects.filter(user=request.user, organization_id=request.user.organization_id).first()
        if mailbox is None:
            raise serializers.ValidationError({"detail": "Connect your mailbox first."})
        try:
            # No recipient supplied by the client; this endpoint cannot send
            # arbitrary messages or turn Homebase into a mail relay.
            send_connected(request.user, mailbox.email, "Homebase Expenses - connection test",
                "Your Homebase Expenses email connection can send messages. This is a test email.")
        except Exception:
            raise serializers.ValidationError({"detail": "The test was not confirmed. Check your connection before trying again."}) from None
        return Response({"detail": "Your provider accepted the test email. Check your inbox and spam folder."})
