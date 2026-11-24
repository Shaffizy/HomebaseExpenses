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
    title = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects.none(), required=False, allow_null=True)
    category_name = serializers.SerializerMethodField()
    expense_category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    category_is_active = serializers.BooleanField(source="category.is_active", read_only=True, default=False)
    department = serializers.ChoiceField(choices=Expense.Department.choices, required=False)
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
        user = self.context["request"].user
        if user.role in (Role.REQUESTER, Role.REVIEWER):
            if user.department not in Expense.Department.values:
                raise serializers.ValidationError({"department": "Ask your administrator to assign your department before creating or editing an expense."})
            if "department" in attrs and attrs["department"] != user.department:
                raise serializers.ValidationError({"department": "You can only raise expenses for your assigned department."})
            attrs["department"] = user.department
        category = attrs.get("category")
        if category is not None and not category.is_active:
            raise serializers.ValidationError({"category": "This category is inactive."})
        selected_category = attrs.get("category", self.instance.category if self.instance else None)
        if "title" not in attrs:
            if selected_category and (self.instance is None or "category" in attrs or not self.instance.title):
                attrs["title"] = selected_category.name
            elif self.instance is None:
                raise serializers.ValidationError({"category": "Select a category before saving the expense."})
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
    wht_classification = serializers.CharField(read_only=True)
    wht_classification_label = serializers.SerializerMethodField()
    wht_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    wht_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_total = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=ExpenseStatus.choices, read_only=True)
    expense_number = serializers.CharField(read_only=True)
    assigned_reviewer = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_reviewer_name = serializers.CharField(source="assigned_reviewer.name", read_only=True, default=None)
    reviewed_by = serializers.PrimaryKeyRelatedField(read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.name", read_only=True, default=None)
    reviewed_at = serializers.DateTimeField(read_only=True)
    fincon_reviewed_by = serializers.PrimaryKeyRelatedField(read_only=True)
    fincon_reviewed_by_name = serializers.CharField(source="fincon_reviewed_by.name", read_only=True, default=None)
    fincon_reviewed_at = serializers.DateTimeField(read_only=True)
    assigned_approver = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_approver_name = serializers.CharField(
        source="assigned_approver.name", read_only=True, default=None
    )

    def get_wht_classification_label(self, expense):
        return expense.get_wht_classification_display() if expense.wht_classification else ""

    def get_net_total(self, expense):
        net = (expense.total - (expense.wht_amount or Decimal("0.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{net:.2f}"

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_number",
            "title",
            "category",
            "category_name",
            "expense_category_name",
            "category_is_active",
            "department",
            "branch",
            "requested_by",
            "due_date",
            "currency",
            "status",
            "total",
            "wht_classification",
            "wht_classification_label",
            "wht_rate",
            "wht_amount",
            "net_total",
            "items",
            "assigned_reviewer",
            "assigned_reviewer_name",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "fincon_reviewed_by",
            "fincon_reviewed_by_name",
            "fincon_reviewed_at",
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
            "wht_classification",
            "wht_classification_label",
            "wht_rate",
            "wht_amount",
            "net_total",
            "created_by",
            "assigned_reviewer_name",
            "reviewed_by_name",
            "fincon_reviewed_by_name",
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
        wht_amount = (expense.total * (expense.wht_rate or Decimal("0.00")) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expense.wht_amount = wht_amount
        expense.net_total = (expense.total - wht_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expense.save(update_fields=["total", "wht_amount", "net_total", "updated_at"])

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
