from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Role(models.TextChoices):
    REQUESTER = "REQUESTER", "Requester"
    REVIEWER = "REVIEWER", "Reviewer"
    APPROVER = "APPROVER", "Approver"
    ADMIN = "ADMIN", "Admin"


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "organizations"

    def __str__(self):
        return self.name


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="users"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    signature_data = models.TextField(blank=True, default="", editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization"], condition=models.Q(role="APPROVER", is_active=True), name="one_active_approver_per_org"),
            models.CheckConstraint(condition=models.Q(role__in=["REQUESTER", "REVIEWER", "APPROVER", "ADMIN"]), name="valid_expense_user_role"),
        ]

    def save(self, *args, **kwargs):
        self.is_staff = self.role == Role.ADMIN
        if self.role != Role.ADMIN:
            self.is_superuser = False
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_staff", "is_superuser"}
        super().save(*args, **kwargs)

    # Throttle login attempts per user before a short cooldown kicks in.
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    def register_failed_login(self) -> bool:
        """Record a failed attempt; lock the account for 5 minutes after 5 failures."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            self.failed_login_attempts = 0
            self.locked_until = timezone.now() + timedelta(minutes=5)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def register_successful_login(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    @property
    def name(self):
        full = self.get_full_name()
        return full or self.username

    def __str__(self):
        return f"{self.username} ({self.role})"


class ConnectedMailbox(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mailbox")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    provider = models.CharField(max_length=10, choices=[("gmail", "Gmail"), ("zoho", "Zoho")])
    email = models.EmailField()
    encrypted_token = models.TextField()
    account_id = models.CharField(max_length=100, blank=True)
    needs_reconnect = models.BooleanField(default=False)
    checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), "organization", name="unique_connected_mailbox_per_org")]


class MailboxAuthorization(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state_hash = models.CharField(max_length=64, unique=True)
    provider = models.CharField(max_length=10)
    expected_email = models.EmailField()
    verifier = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
