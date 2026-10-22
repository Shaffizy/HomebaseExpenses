import os

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create Homebase's private mailbox encryption key once, without printing it."

    def handle(self, *args, **options):
        path = settings.BASE_DIR / ".email-token.key"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self.stdout.write("Existing key preserved. No changes made.")
            return
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(Fernet.generate_key())
        self.stdout.write("Private email encryption key created. Back it up securely; never commit it.")
