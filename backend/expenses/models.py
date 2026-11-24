
from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from simple_history.models import HistoricalRecords

from accounts.models import Department, Organization, User
from .evidence import evidence_path, evidence_storage


class ExpenseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "Awaiting review"
    IN_FINCON_REVIEW = "IN_FINCON_REVIEW", "Awaiting FinCon review"
    SUBMITTED = "SUBMITTED", "Awaiting approval"
    APPROVED = "APPROVED", "Approved"
    RETURNED = "RETURNED", "Returned"
    REJECTED = "REJECTED", "Rejected"
    CLOSED = "CLOSED", "Closed"


class WhtClassification(models.TextChoices):
    NON_TAXABLE_0 = "NON_TAXABLE_0", "Non-Taxable (0%) — Health Related / HMO / Exempt"
    RATE_2_NETWORK_DATA = "RATE_2_NETWORK_DATA", "2% — Network Infrastructure & Data Services (MTN, IPNX, Cobranet)"
    RATE_2_SUPPLY_GOODS = "RATE_2_SUPPLY_GOODS", "2% — Supply of Goods / General Commerce"
    RATE_2_AGRO = "RATE_2_AGRO", "2% — Agriculture & Agro-Allied (Raw Farm Produce, Primary Production, Agro-Processing)"
    RATE_2_CONSTRUCTION = "RATE_2_CONSTRUCTION", "2% — Civil Engineering, Building & Infrastructure Development"
    RATE_5_TECH_ICT = "RATE_5_TECH_ICT", "5% — ICT, Software Licensing, Cloud Hosting, IT Consultancy & Managed Services"
    RATE_5_PROFESSIONAL = "RATE_5_PROFESSIONAL", "5% — Professional, Legal, Accounting, Management Consultancy, Financial & Insurance Services"
    RATE_5_SUBCONTRACT_PROPERTY = "RATE_5_SUBCONTRACT_PROPERTY", "5% — Specialized Sub-Contracting (Electrical, Plumbing), Property Management & Agro Services"
    RATE_5_COMMERCE_SERVICES = "RATE_5_COMMERCE_SERVICES", "5% — Logistics, Freight, Transport, Advertising, Marketing, Events & Commissions"
    RATE_5_NON_RESIDENT_INFRA = "RATE_5_NON_RESIDENT_INFRA", "5% (Non-Resident) — Network Infrastructure, Building & Civil Engineering"
    RATE_10_RENT_LEASE = "RATE_10_RENT_LEASE", "10% — Commercial & Residential Property Rent or Lease"
    RATE_10_DIRECTORS_ROYALTIES = "RATE_10_DIRECTORS_ROYALTIES", "10% (Resident) — Directors' Fees, Royalties & Intellectual Property"
    RATE_10_NON_RESIDENT_SERVICES = "RATE_10_NON_RESIDENT_SERVICES", "10% (Non-Resident) — Professional, ICT, Consultancy, Supply of Goods & General Services"
    RATE_20_NON_RESIDENT_DIRECTORS_ROYALTIES = "RATE_20_NON_RESIDENT_DIRECTORS_ROYALTIES", "20% (Non-Resident) — Directors' Fees, Royalties & Intellectual Property"


WHT_CLASSIFICATION_RATES = {
    WhtClassification.NON_TAXABLE_0: Decimal("0.00"),
    WhtClassification.RATE_2_NETWORK_DATA: Decimal("2.00"),
    WhtClassification.RATE_2_SUPPLY_GOODS: Decimal("2.00"),
    WhtClassification.RATE_2_AGRO: Decimal("2.00"),
    WhtClassification.RATE_2_CONSTRUCTION: Decimal("2.00"),
    WhtClassification.RATE_5_TECH_ICT: Decimal("5.00"),
    WhtClassification.RATE_5_PROFESSIONAL: Decimal("5.00"),
    WhtClassification.RATE_5_SUBCONTRACT_PROPERTY: Decimal("5.00"),
    WhtClassification.RATE_5_COMMERCE_SERVICES: Decimal("5.00"),
    WhtClassification.RATE_5_NON_RESIDENT_INFRA: Decimal("5.00"),
    WhtClassification.RATE_10_RENT_LEASE: Decimal("10.00"),
    WhtClassification.RATE_10_DIRECTORS_ROYALTIES: Decimal("10.00"),
    WhtClassification.RATE_10_NON_RESIDENT_SERVICES: Decimal("10.00"),
    WhtClassification.RATE_20_NON_RESIDENT_DIRECTORS_ROYALTIES: Decimal("20.00"),
}


class ExpenseCategory(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="expense_categories")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="expense_categories_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(
            Lower("name"), "organization", name="unique_expense_category_per_org")]

    def __str__(self):
        return self.name


class Expense(models.Model):
    Department = Department
    WhtClassification = WhtClassification
    WHT_RATES = WHT_CLASSIFICATION_RATES

    class Branch(models.TextChoices):
        LAGOS = "Lagos", "Lagos"
        ABUJA = "Abuja", "Abuja"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="expenses"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="expenses_created"
    )
    expense_number = models.CharField(max_length=64)
    # Retain legacy text for existing records; new requests use controlled fields.
    title = models.CharField(max_length=255, blank=True, default="")
    vendor_name = models.CharField(max_length=255, blank=True, default="")
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses")
    department = models.CharField(
        max_length=20, choices=Department.choices, blank=True, default="")
    branch = models.CharField(
        max_length=10, choices=Branch.choices, blank=True, default="")
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(
        max_length=20, choices=ExpenseStatus.choices, default=ExpenseStatus.DRAFT
    )
    assigned_reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="review_expenses")
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    fincon_reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses_fincon_reviewed")
    fincon_reviewed_at = models.DateTimeField(null=True, blank=True)
    wht_classification = models.CharField(max_length=48, choices=WhtClassification.choices, blank=True, default="")
    wht_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    wht_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    net_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="expense_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_signature_data = models.TextField(blank=True, default="", editable=False)
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords(excluded_fields=["approved_signature_data"])

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "expense_number"],
                name="unique_expense_number_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.expense_number} - {self.title} [{self.status}]"


class ExpenseItem(models.Model):
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.description} x{self.quantity}"


class ExpenseNumberSequence(models.Model):
    """Per-org per-year counter so expense numbers are generated automatically."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "year"],
                name="unique_seq_per_org_year",
            )
        ]

    @classmethod
    def next_number(cls, organization) -> str:
        from django.db import transaction

        year = timezone.now().year
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                organization=organization, year=year
            )
            seq.last_number += 1
            seq.save(update_fields=["last_number"])
        return f"EXP-{year}-{seq.last_number:04d}"


class ExpenseEvidence(models.Model):
    class Category(models.TextChoices):
        BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE", "Birth certificate"
        IDENTIFICATION = "IDENTIFICATION", "Proof of identification"
        APPLICATION_LETTER = "APPLICATION_LETTER", "Application letter"
        ACCOUNT_STATEMENT = "ACCOUNT_STATEMENT", "Statement of account"
        INVOICE_RECEIPT = "INVOICE_RECEIPT", "Invoice / receipt"
        OTHER = "OTHER", "Other"

    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="evidence")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    category = models.CharField(max_length=32, choices=Category.choices)
    label = models.CharField(max_length=150, blank=True)
    file = models.FileField(storage=evidence_storage, upload_to=evidence_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


@receiver(post_delete, sender=ExpenseEvidence)
def delete_evidence_file(sender, instance, **kwargs):
    storage, name = instance.file.storage, instance.file.name
    transaction.on_commit(lambda: storage.delete(name))


class Comment(models.Model):
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="comments"
    )
    text = models.TextField()
    stage_history_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on expense {self.expense_id} by {self.author.username}"
