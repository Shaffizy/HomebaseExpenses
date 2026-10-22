from datetime import datetime, timezone

import pytest

from accounts.models import Organization
from expenses.models import ExpenseNumberSequence


@pytest.mark.django_db
def test_expense_prefix_and_existing_sequence_continue(monkeypatch):
    monkeypatch.setattr("expenses.models.timezone.now", lambda: datetime(2026, 10, 16, tzinfo=timezone.utc))
    organization = Organization.objects.create(name="Homebase references")
    ExpenseNumberSequence.objects.create(organization=organization, year=2026, last_number=2)
    assert ExpenseNumberSequence.next_number(organization) == "EXP-2026-0003"
    assert ExpenseNumberSequence.next_number(organization) == "EXP-2026-0004"


@pytest.mark.django_db
def test_expense_sequence_is_scoped_to_organization_and_year(monkeypatch):
    monkeypatch.setattr("expenses.models.timezone.now", lambda: datetime(2026, 10, 16, tzinfo=timezone.utc))
    organization = Organization.objects.create(name="First")
    other = Organization.objects.create(name="Second")
    assert ExpenseNumberSequence.next_number(organization) == "EXP-2026-0001"
    assert ExpenseNumberSequence.next_number(other) == "EXP-2026-0001"
    monkeypatch.setattr("expenses.models.timezone.now", lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert ExpenseNumberSequence.next_number(organization) == "EXP-2027-0001"
