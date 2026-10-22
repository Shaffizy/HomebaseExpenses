from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from .models import Role, User
from .signatures import SignatureUploadSerializer


class SignatureWriteThrottle(UserRateThrottle):
    scope = "signature"
    rate = "10/hour"


class SignatureView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        return [SignatureWriteThrottle()] if self.request.method in {"POST", "DELETE"} else super().get_throttles()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.check_approver(request.user)

    @staticmethod
    def check_approver(user):
        if user.role != Role.APPROVER or user.is_staff or not user.is_active:
            raise PermissionDenied("Only approvers can manage their own signature.")

    def get(self, request):
        return Response({"signature_data": request.user.signature_data})

    @transaction.atomic
    def post(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        self.check_approver(user)
        serializer = SignatureUploadSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        user.signature_data = serializer.validated_data["file"]
        user.save(update_fields=["signature_data"])
        return Response({"signature_data": user.signature_data})

    @transaction.atomic
    def delete(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        self.check_approver(user)
        password = request.data.get("current_password", "")
        if not isinstance(password, str) or not user.check_password(password):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        user.signature_data = ""
        user.save(update_fields=["signature_data"])
        return Response(status=204)
