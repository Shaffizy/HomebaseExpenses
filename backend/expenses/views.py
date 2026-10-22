from django.db.models import Q
from django.db import transaction, IntegrityError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from accounts.models import Role
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Expense, ExpenseStatus, Comment, ExpenseCategory
from .permissions import ExpenseAccessPermission, CategoryAccessPermission
from .serializers import ExpenseSerializer, CommentSerializer, ExpenseEvidenceSerializer, ExpenseCategorySerializer
from .services import (
    TransitionError,
    can_comment,
    close_expense,
    transition,
    current_stage_comment,
    current_stage_record,
)

# bookkeeping fields that are not interesting in a history diff
HISTORY_EXCLUDE = {
    "id",
    "created_at",
    "updated_at",
    "history_id",
    "history_type",
    "history_user",
    "history_date",
    "history_change_reason",
}
HISTORY_TYPE_LABEL = {"+": "create", "-": "delete", "~": "update"}


def _record_fields(record) -> dict:
    return {
        field.attname: getattr(record, field.attname)
        for field in record._meta.local_fields
        if not field.name.startswith("history_")
    }


def _diff_records(records, source: str) -> list[dict]:
    """Turn an ordered (oldest first) list of simple-history records into
    entries of {date, user, type, source, changes}."""
    entries = []
    previous = None
    for record in records:
        current = _record_fields(record)
        old = _record_fields(previous) if previous is not None else {}
        changes = {}
        for field, new_value in current.items():
            if field in HISTORY_EXCLUDE:
                continue
            old_value = old.get(field)
            if old_value != new_value:
                changes[field] = [old_value, new_value]
        if record.history_type == "~" and not changes:
            previous = record
            continue
        entries.append(
            {
                "date": record.history_date,
                "user": record.history_user.username
                if record.history_user_id
                else None,
                "type": HISTORY_TYPE_LABEL.get(record.history_type, record.history_type),
                "source": source,
                "changes": changes,
            }
        )
        previous = record
    return entries


def expense_history(expense: Expense) -> list[dict]:
    from .models import HistoricalExpenseItem

    expense_entries = _diff_records(
        sorted(expense.history.all(), key=lambda r: (r.history_date, r.history_id)),
        "expense",
    )
    item_records = sorted(
        HistoricalExpenseItem.objects.filter(expense_id=expense.id),
        key=lambda r: (r.history_date, r.history_id),
    )
    item_entries = _diff_records(item_records, "item")
    return sorted(
        expense_entries + item_entries, key=lambda e: e["date"], reverse=True
    )


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, ExpenseAccessPermission]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = (
            Expense.objects.filter(organization=self.request.user.organization)
            .select_related("created_by", "organization", "assigned_approver", "approved_by", "category")
            .prefetch_related("items")
        )
        if self.request.user.role == Role.REQUESTER:
            queryset = queryset.filter(created_by=self.request.user)
        if self.action == "list":
            queryset = queryset.defer("approved_signature_data")
        status_param = self.request.query_params.get("status")
        if status_param in ExpenseStatus.values:
            queryset = queryset.filter(status=status_param)
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(expense_number__icontains=search)
                | Q(category__name__icontains=search) | Q(title__icontains=search)
                | Q(department__icontains=search) | Q(branch__icontains=search)
            )
        return queryset

    @action(detail=False, methods=["get"])
    def options(self, request):
        return Response({
            "departments": [{"value": value, "label": label} for value, label in Expense.Department.choices],
            "branches": [{"value": value, "label": label} for value, label in Expense.Branch.choices],
        })

    def _run_action(self, request, action_name: str):
        expense = self.get_object()
        try:
            expense = transition(
                expense, request.user, action_name, comment=request.data.get("comment")
            )
        except TransitionError as exc:
            return Response({"detail": exc.message}, status=exc.status_code)
        return Response(ExpenseSerializer(expense, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._run_action(request, "submit")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._run_action(request, "approve")

    @action(detail=True, methods=["post"], url_path="return", url_name="return")
    def return_expense(self, request, pk=None):
        return self._run_action(request, "return")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._run_action(request, "reject")

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        expense = self.get_object()
        if request.method == "GET":
            queryset = expense.comments.select_related("author").all()
            return Response(CommentSerializer(queryset, many=True).data)

        text = request.data.get("text")
        if not isinstance(text, str):
            return Response({"detail": "Text must be a string."}, status=400)
        text = text.strip()
        if not text:
            return Response({"detail": "Text is required."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(pk=expense.pk)
            if not can_comment(request.user, expense):
                return Response({"detail": "You cannot comment on this expense."}, status=403)
            stage = current_stage_record(expense)
            comment = Comment.objects.create(expense=expense, author=request.user, text=text, stage_history_id=stage.history_id)
        return Response(CommentSerializer(comment).data, status=201)

    @action(detail=True, methods=["get"], url_path="action-comment")
    def action_comment(self, request, pk=None):
        expense = self.get_object()
        comment = current_stage_comment(expense, request.user) if can_comment(request.user, expense) else None
        return Response(CommentSerializer(comment).data if comment else None)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        expense = self.get_object()
        try:
            expense = close_expense(expense, request.user)
        except TransitionError as exc:
            return Response({"detail": exc.message}, status=exc.status_code)
        return Response(ExpenseSerializer(expense, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        expense = self.get_object()
        return Response(expense_history(expense))

    def _can_manage_evidence(self, user, expense):
        return user.role == Role.REQUESTER and expense.created_by_id == user.id and expense.status in (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED)

    @action(detail=True, methods=["get", "post"])
    def evidence(self, request, pk=None):
        expense = self.get_object()
        if request.method == "GET":
            return Response(ExpenseEvidenceSerializer(expense.evidence.all(), many=True).data)
        serializer = ExpenseEvidenceSerializer(data=request.data)
        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(pk=expense.pk)
            if not self._can_manage_evidence(request.user, expense):
                return Response({"detail": "Only the expense owner can attach evidence to a draft or returned expense."}, status=403)
            serializer.is_valid(raise_exception=True)
            file = serializer.validated_data["file"]
            serializer.save(expense=expense, uploaded_by=request.user, original_name=file.name, size=file.size)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["get", "delete"], url_path=r"evidence/(?P<evidence_id>[0-9]+)")
    def evidence_document(self, request, pk=None, evidence_id=None):
        expense = self.get_object()
        if request.method == "GET":
            document = get_object_or_404(expense.evidence, pk=evidence_id)
            response = FileResponse(document.file.open("rb"), as_attachment=True, filename=document.original_name, content_type="application/octet-stream")
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "private, no-store"
            return response
        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(pk=expense.pk)
            if not self._can_manage_evidence(request.user, expense):
                return Response({"detail": "Evidence cannot be removed from this expense."}, status=403)
            document = get_object_or_404(expense.evidence, pk=evidence_id)
            document.delete()
        return Response(status=204)

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, CategoryAccessPermission]
    pagination_class = None

    def get_queryset(self):
        queryset = ExpenseCategory.objects.filter(organization=self.request.user.organization)
        if self.request.user.role != Role.ADMIN or self.request.query_params.get("include_inactive") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(organization=self.request.user.organization, created_by=self.request.user)
        except IntegrityError:
            raise ValidationError({"name": "This category already exists."})

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise ValidationError({"name": "This category already exists."})

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        category.is_active = False
        category.save(update_fields=["is_active"])
        return Response(status=204)
