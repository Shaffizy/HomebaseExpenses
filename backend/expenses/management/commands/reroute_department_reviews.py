from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from simple_history.utils import update_change_reason
from accounts.models import Department, Role, User
from expenses.models import Expense, ExpenseStatus
from expenses.notifications import notify_next_role


class Command(BaseCommand):
    help = "Preview pending review routing by department; --apply saves only reviewer assignments."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save the previewed department routing.")

    def handle(self, *args, **options):
        with transaction.atomic():
            pending = list(Expense.objects.select_for_update().filter(status=ExpenseStatus.IN_REVIEW).order_by("pk"))
            changes = []
            missing = []
            for expense in pending:
                reviewers = User.objects.filter(organization_id=expense.organization_id, role=Role.REVIEWER, is_active=True, department=expense.department).exclude(pk=expense.created_by_id).order_by("pk")
                reviewer = reviewers.filter(pk=expense.assigned_reviewer_id).first() or reviewers.first()
                if expense.department not in Department.values or reviewer is None:
                    missing.append(expense.pk)
                    continue
                if expense.assigned_reviewer_id != reviewer.pk:
                    changes.append((expense, reviewer))
            self.stdout.write(f"Pending reviews: {len(pending)}; assignments to change: {len(changes)}; missing department/reviewer: {len(missing)}.")
            if missing:
                self.stdout.write("Configure departments and active reviewers for expense IDs: " + ", ".join(map(str, missing)))
                if options["apply"]:
                    raise CommandError("No changes saved. Configure missing department reviewers first.")
            if not options["apply"]:
                self.stdout.write("Preview only. Nothing saved or emailed. Run with --apply after checking assignments.")
                return
            for expense, reviewer in changes:
                expense.assigned_reviewer = reviewer
                expense.save(update_fields=["assigned_reviewer", "updated_at"])
                update_change_reason(expense, "Pending review routed to department reviewer")
                transaction.on_commit(lambda expense=expense: notify_next_role(expense))
            self.stdout.write(self.style.SUCCESS(f"Updated {len(changes)} pending review assignments. Other statuses were not changed."))
