import secrets
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import Organization, Role, User

class Command(BaseCommand):
    help = "Create Homebase demo accounts without changing existing passwords."
    @transaction.atomic
    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(name="Homebase Mortgage Bank")
        for username, role in [("requester", Role.REQUESTER), ("approver", Role.APPROVER), ("admin", Role.ADMIN)]:
            existing = User.objects.filter(username=username).first()
            if existing:
                if existing.organization_id != org.pk or existing.role != role:
                    raise CommandError(f"Username {username} belongs to a different account.")
                self.stdout.write(f"{username}: existing password unchanged")
                continue
            if role == Role.APPROVER and org.users.filter(role=role, is_active=True).exists():
                self.stdout.write("An approver already exists; skipped")
                continue
            password = secrets.token_urlsafe(16)
            User.objects.create_user(username=username, email=f"{username}@homebase.demo", password=password, role=role, organization=org, is_superuser=role == Role.ADMIN)
            self.stdout.write(f"{username} | {role} | password: {password}")
