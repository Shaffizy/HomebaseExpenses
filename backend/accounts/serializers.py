from django.contrib.auth.password_validation import validate_password, password_changed
from django.core.exceptions import ValidationError as PasswordError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework.exceptions import AuthenticationFailed
from secrets import compare_digest
from .models import Organization, Role, User

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]

class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    isStaff = serializers.BooleanField(source="is_staff", read_only=True)
    organization = OrganizationSerializer(read_only=True)
    class Meta:
        model = User
        fields = ["id", "name", "role", "is_staff", "isStaff", "organization"]

class UserAdminSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    class Meta:
        model = User
        fields = ["id", "username", "name", "email", "first_name", "last_name", "role", "organization", "is_active", "is_staff", "date_joined", "last_login"]

class AccountRules:
    def validate(self, attrs):
        admin = self.context["request"].user
        user = self.instance
        role = attrs.get("role", user.role if user else None)
        active = attrs.get("is_active", user.is_active if user else True)
        if user and user.pk == admin.pk and (role != Role.ADMIN or not active):
            raise serializers.ValidationError("You cannot remove your own administrator access.")
        if user and role == Role.ADMIN and user.role != Role.ADMIN:
            raise serializers.ValidationError({"role": "Administrator privileges are not granted through this form."})
        if role == Role.APPROVER and active:
            others = User.objects.filter(organization=admin.organization, role=Role.APPROVER, is_active=True)
            if user:
                others = others.exclude(pk=user.pk)
            if others.exists():
                raise serializers.ValidationError({"role": "There can be only one active approver."})
        if "password" in attrs:
            try:
                validate_password(attrs["password"], User(username=attrs.get("username", user.username if user else ""), email=attrs.get("email", user.email if user else "")))
            except PasswordError as exc:
                raise serializers.ValidationError({"password": exc.messages})
        return attrs

class RegisterUserSerializer(AccountRules, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=[Role.REQUESTER, Role.REVIEWER, Role.APPROVER])
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "password", "is_active"]
        read_only_fields = ["id"]
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(organization=self.context["request"].user.organization, **validated_data)
        user.set_password(password)
        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            raise serializers.ValidationError("Username conflict or an active approver already exists.")
        return user

class UserUpdateSerializer(AccountRules, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, min_length=8, max_length=1024)
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "is_active", "password"]
        read_only_fields = ["id"]
    def update(self, instance, validated_data):
        try:
            with transaction.atomic():
                password = validated_data.pop("password", None)
                if password is not None:
                    instance.set_password(password)
                    instance.failed_login_attempts = 0
                    instance.locked_until = None
                updated = super().update(instance, validated_data)
                if password is not None:
                    password_changed(password, updated)
                return updated
        except IntegrityError:
            raise serializers.ValidationError("Username conflict or an active approver already exists.")

class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)

    def validate(self, attrs):
        user = self.instance
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if user.check_password(attrs["new_password"]):
            raise serializers.ValidationError({"new_password": "Choose a password different from your current password."})
        try:
            validate_password(attrs["new_password"], user)
        except PasswordError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs

class PasswordAwareRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        user = User.objects.filter(**{api_settings.USER_ID_FIELD: token.get(api_settings.USER_ID_CLAIM)}).first()
        if user is None or not user.is_active or not compare_digest(str(token.get(api_settings.REVOKE_TOKEN_CLAIM, "")), get_md5_hash_password(user.password)):
            raise AuthenticationFailed("Please sign in again.")
        return super().validate(attrs)
