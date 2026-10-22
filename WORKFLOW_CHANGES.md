# Two-role workflow changes
## Implemented
REQUESTER creates a draft and submits directly to the organization's one active
APPROVER. The approver can approve, return, or reject a submitted expense.
ADMIN is a separate account-management role, not a workflow participant.
Returned expenses can be edited and resubmitted by their creator.
The inherited owner-only Close action is still available for draft-like states.

## Backend file map
- accounts/models.py: REQUESTER, APPROVER, ADMIN roles; removed reviewer/personal
  routing fields; partial unique database constraint for one active approver per
  organization; staff privileges follow the ADMIN role.
- accounts/serializers.py: admin registration creates requesters/approvers;
  password validation, single-approver validation, and no client-granted admin
  privilege. Editing/reactivating also respects the single-approver limit.
- accounts/permissions.py: account management requires authenticated active ADMIN.
- accounts/views.py: organization-scoped management; stable user ordering;
  deactivation preserves users and their historical expense records.
- accounts/urls.py: removed reviewer-list and organization-routing endpoints.
- accounts/admin.py: removed obsolete assignment fields from Django admin.
- accounts/management/commands/seed_demo.py: one Homebase organization,
  requester/approver/admin; generated demo passwords printed once and existing
  passwords are not reset.
- expenses/models.py: removed REVIEWED and reviewer routing; added approved_by
  and approved_at; comments link to the exact current-stage history record.
- expenses/serializers.py: routing/approval fields are server-controlled;
  nested item writes are transactional; totals remain calculated on the server.
- expenses/services.py: direct transition table, owner/organization checks,
  active approver lookup, row locking, atomic status/comment writes, and
  current-stage comment reuse without duplicates.
- expenses/permissions.py: only the requester who created the draft/returned
  expense may edit/delete; admins and approvers cannot edit ticket fields.
- expenses/views.py: requesters see only their own expenses; organization-scoped
  approver/admin reads; no Forward endpoint; locked inline comment writes.
- expenses/notifications.py: disabled until email recipients/delivery are agreed.
- accounts/migrations/0008_*.py and expenses/migrations/0007_*.py, 0008_*.py:
  record these schema changes. Generated but NOT applied to PostgreSQL.
- config/test_settings.py: disposable SQLite database for local testing only.
  This does not replace testing PostgreSQL locking/concurrency.
- expenses/test_workflow.py: role/status/action matrix plus authentication,
  admin, single-approver, ownership, totals, evidence, comment reuse and approval
  attribution checks. Obsolete copied three-role tests are preserved under
  HomebaseExpenses-Step2Backup/legacy-three-role-tests.

## Frontend file map
- pages/AdminPage.jsx: requester/approver registration; no routing selectors;
  edit/deactivate users; administrator accounts stay separate.
- components/ExpenseActions.jsx: Approve/Return/Reject on SUBMITTED; no Forward;
  reuse a posted current-stage reason or show the required comment dialog.
- components/CommentThread.jsx: approver comments on SUBMITTED; requester replies
  on RETURNED.
- components/ExpenseForm.jsx and pages/ExpenseFormPage.jsx: requester access,
  removed reviewer selector; optional evidence remains available.
- pages/ExpenseDetailPage.jsx: removed reviewer reassignment controls.
- pages/ExpensesPage.jsx and DashboardPage.jsx: requester/approver labels and
  direct approval queues.
- lib/types.js, lib/api.js, components/StatusTimeline.jsx and ui.jsx:
  removed REVIEWED/Forward.
- components/Layout.jsx: Homebase expense branding.
- AssigneePicker.jsx: retired because individual reviewer routing no longer exists.

## Verify locally
Install this project's backend dependencies before using its own virtual environment:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py check
.venv\Scripts\python -m pytest --ds=config.test_settings -q
```
Tests use a disposable database; they do not populate the actual Homebase database.
Frontend:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\frontend
npm run build
npm run dev
```
The preview is http://127.0.0.1:5174; live login still requires a configured running
backend/database. Do not migrate or seed PostgreSQL yet: expense-specific ticket
fields must be finished first.

## Still to do
Replace title/vendor/due-date with the agreed paper-format purpose, department,
and ticket date fields. Finalize requester identity display, particulars and
unit-cost labels. Build the printable approved document. Configure real emails
only after recipients and delivery are authorized. Perform browser and
PostgreSQL integration/concurrency testing.
