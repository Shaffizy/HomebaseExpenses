from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from django.db import transaction

from accounts.models import Role, User

from .models import Expense, ExpenseItem, ExpenseStatus, Comment, ExpenseEvidence, ExpenseCategory
from .evidence import validate_document


class ExpenseEvidenceSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, validators=[validate_document])

    class Meta:
        model = ExpenseEvidence
        fields = ["id", "category", "label", "file", "original_name", "size", "uploaded_by", "created_at"]
        read_only_fields = ["id", "original_name", "size", "uploaded_by", "created_at"]

    def validate(self, attrs):
        if attrs.get("category") == ExpenseEvidence.Category.OTHER and not attrs.get("label", "").strip():
            raise serializers.ValidationError({"label": "Name the document when choosing Other."})
        return attrs


class ExpenseItemSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ExpenseItem
        fields = ["id", "description", "quantity", "unit_price", "line_total"]
        read_only_fields = ["id"]


class ExpenseCategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=100, allow_blank=False)
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        validators = []

    def validate_name(self, value):
        queryset = ExpenseCategory.objects.filter(organization=self.context["request"].user.organization, name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This category already exists.")
        return value


class ExpenseSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects.none(), required=False, allow_null=True)
    category_name = serializers.SerializerMethodField()
    category_is_active = serializers.BooleanField(source="category.is_active", read_only=True, default=False)
    department = serializers.ChoiceField(choices=Expense.Department.choices)
    branch = serializers.ChoiceField(choices=Expense.Branch.choices)
    currency = serializers.ChoiceField(choices=["NGN"], default="NGN")
    requested_by = serializers.CharField(source="created_by.name", read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            self.fields["category"].queryset = ExpenseCategory.objects.filter(organization=request.user.organization, is_active=True)
        if getattr(self.context.get("view"), "action", None) == "list":
            self.fields.pop("approved_signature_data", None)

    def get_category_name(self, expense):
        return expense.title or (expense.category.name if expense.category_id else "Untitled expense")

    def validate(self, attrs):
        category = attrs.get("category")
        if category is not None and not category.is_active:
            raise serializers.ValidationError({"category": "This category is inactive."})
        items = attrs.get("items")
        if items is not None:
            total = sum(((item["quantity"] * item["unit_price"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for item in items), Decimal("0.00"))
            if total > Decimal("999999999999.99"):
                raise serializers.ValidationError({"items": "Overall cost exceeds the supported amount."})
        return attrs

    items = ExpenseItemSerializer(many=True)
    approved_by_name = serializers.CharField(source="approved_by.name", read_only=True, default=None)
    approved_by = serializers.PrimaryKeyRelatedField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)
    approved_signature_data = serializers.CharField(read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    status = serializers.ChoiceField(choices=ExpenseStatus.choices, read_only=True)
    expense_number = serializers.CharField(read_only=True)
    assigned_approver = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_approver_name = serializers.CharField(
        source="assigned_approver.name", read_only=True, default=None
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_number",
            "title",
            "category",
            "category_name",
            "category_is_active",
            "department",
            "branch",
            "requested_by",
            "due_date",
            "currency",
            "status",
            "total",
            "items",
            "assigned_approver",
            "assigned_approver_name",
            "created_by",
            "created_at",
            "updated_at",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "approved_signature_data",
        ]
        read_only_fields = [
            "id",
            "expense_number",
            "status",
            "total",
            "created_by",
            "assigned_approver_name",
            "created_at",
            "updated_at",
        ]

    def _write_items(self, expense: Expense, items: list) -> None:
        expense.items.all().delete()
        total = Decimal("0.00")
        for item in items:
            line = ExpenseItem.objects.create(expense=expense, **item)
            total += line.line_total
        expense.total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expense.save(update_fields=["total", "updated_at"])

    @transaction.atomic
    def create(self, validated_data):
        from .models import ExpenseNumberSequence

        items = validated_data.pop("items", [])
        request = self.context["request"]
        org = request.user.organization
        expense = Expense.objects.create(
            organization=org,
            created_by=request.user,
            expense_number=ExpenseNumberSequence.next_number(org),
            **validated_data,
        )
        self._write_items(expense, items)
        return expense

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items is not None:
            self._write_items(instance, items)
        return instance


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "author_name", "text", "created_at"]
        read_only_fields = ["id", "author", "author_name", "created_at"]
