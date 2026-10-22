import pytest
from django.db import IntegrityError, transaction
from accounts.models import Organization, User, Role
from expenses.models import ExpenseCategory


@pytest.mark.django_db
def test_case_insensitive_category_uniqueness_is_database_enforced():
    organization = Organization.objects.create(name="Integrity test")
    admin = User.objects.create(username="integrity-admin", organization=organization, role=Role.ADMIN)
    ExpenseCategory.objects.create(organization=organization, created_by=admin, name="Travel")
    with pytest.raises(IntegrityError), transaction.atomic():
        ExpenseCategory.objects.create(organization=organization, created_by=admin, name="TRAVEL")
    other = Organization.objects.create(name="Other integrity test")
    ExpenseCategory.objects.create(organization=other, created_by=admin, name="Travel")


@pytest.mark.django_db
def test_one_active_approver_is_database_enforced():
    organization = Organization.objects.create(name="Approver integrity test")
    User.objects.create(username="first-approver", organization=organization, role=Role.APPROVER)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(username="second-approver", organization=organization, role=Role.APPROVER)
    User.objects.create(username="inactive-approver", organization=organization, role=Role.APPROVER, is_active=False)
