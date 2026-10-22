# Homebase Mortgage Bank Expenses
## Current stage
The API prefix is /api/expenses/. The workflow is REQUESTER -> one active APPROVER,
with a separate ADMIN role. Expenses, categories, invoice attachments, comments,
audit history, signatures, approved-slip downloads and shared email delivery are implemented.
The current local database is Microsoft SQL Server. See SQLSERVER_SETUP.md for
setup, tests, migration notes and the PostgreSQL rollback path. The PostgreSQL/Docker
instructions below are retained as historical reference, not the current startup procedure.
The frontend now uses React JavaScript (.jsx components and .js helpers).
The verified pre-conversion source is preserved in the sibling
HomebaseExpenses-Step2Backup folder. It excludes local secrets and uploads.

## Separation from Workflow
- Database: homebase_expenses
- Database user: homebase_expenses_app
- PostgreSQL host port: 5433
- Docker project: homebase-expenses
- Docker volume: homebase-expenses_expenses_pgdata
- Backend development port: 8001
- Frontend development port: 5174 (strict; fails if occupied)
- Uploads: this project's backend/private_evidence directory
- Secrets: a newly generated backend/.env, ignored by Git

The original Workflow database, files, and servers are not modified.
Do not copy the original .env. Environment variables set in your terminal override
.env values; remove inherited billing DB settings before using this project.
The root .env.example is a reference; backend/.env is the active local file.
The localhost sender address is development-only, not a real bank email address.

## Configuration verification
Once this project's dependencies are installed:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py check
```
This checks Django configuration; it does not create database tables.

## Database (when ready)
If Docker Desktop is installed and running:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses
docker compose --env-file backend/.env config --quiet
docker compose --env-file backend/.env up -d db
```
Do not run migrations or seed_demo until the expense schema is agreed.
If Docker is unavailable, a separate local PostgreSQL database/user must be created.
We have not provisioned either database option in this step.

## Servers (after the expense schema is ready)
Backend:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
.venv\Scripts\python manage.py runserver 127.0.0.1:8001
```
Frontend, in another terminal:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\frontend
npm ci
npm run dev
```
Open http://127.0.0.1:5174. Vite forwards /api to port 8001.

## Expense workflow
### Requester-entered expense names

The expense form now uses a required free-text Expense name (maximum 255 characters),
not a predefined category selection. The backend saves it as title and requires a
nonblank name at submission. Department and branch remain controlled dropdowns.
Lists, detail, email and approval slips show the entered name. Existing category
records/relationships remain for compatibility and are not deleted; they are no
longer required for a new expense. The API retains category_name as a compatibility
display field, prioritizing title over an old linked category. No schema migration
is required because the title column already exists.

### Submission email notifications

Each successful submission sends two separate messages: a confirmation to the
requester's registered email, and an action request to the assigned approver.
Both recipients must belong to the expense's organization. Draft saves and failed
transitions send nothing. Delivery starts after the database transaction commits.
Email failures are logged without undoing a submitted expense. Automatic retry
and a delivery queue are not implemented; check backend logs for delivery errors.

One application sender now sends all notifications. Recipients are always the
users' registered email addresses. Requesters receive submission confirmations
and approval/return/rejection updates; the assigned approver receives the request
for approval. Nobody connects a personal Gmail or Zoho account. User logins,
passwords, roles, expense status and existing audit history are unchanged.

### Configure the application sender once

Use backend/.env (not the root example). Set these values using a dedicated
mailbox or your transactional email provider's SMTP credentials:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=Homebase Expenses <your-authorized-sender@example.com>
EMAIL_HOST=your-provider-smtp-host
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password-or-provider-key
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=15
FRONTEND_URL=http://127.0.0.1:5174
```

Your provider must authorize the sender address/domain. Use its specified host,
port and TLS/SSL setting. Gmail testing uses smtp.gmail.com, port 587/TLS and
ONE sender account's Google App Password, not an ordinary Gmail password. A
transactional provider instead supplies SMTP credentials/key; users never need
Google Cloud registration, OAuth test-user approval or individual App Passwords.
Never paste credentials in chat or commit backend/.env. Restart Django after
changing it. A console backend previews mail locally but never delivers it.

### Run and verify

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest accounts/test_email_delivery.py expenses/test_notifications.py -q
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

In a separate terminal:

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\frontend
npm run dev
```

Open http://127.0.0.1:5174/settings?section=email as an administrator. Settings >
Email Notifications shows sender status without revealing credentials. Refresh
status checks configuration only, not delivery. Send test to my email sends a
fixed message ONLY to the signed-in administrator's registered address and is
limited to five attempts per hour. Provider acceptance is not proof of inbox
delivery; check inbox and spam. Incorrect credentials produce a readable error.
The test never submits an expense or emails unrelated recipients.

Requester and approver accounts have no email-connection menu. After configuring
the sender, submit a draft to verify the two organization-scoped notifications.
Use a reachable FRONTEND_URL for recipients outside the development computer.

Personal mailbox endpoints now return 410 to authenticated clients and cannot
connect, check or send email. Their old tables/key are retained, not deleted,
for migration compatibility; old OAuth credentials are unused by notifications.
Any old provider grant can be revoked in the provider's authorized-app settings.

### Spam filtering and test messages

EMAIL_TEST_MODE defaults to DJANGO_DEBUG. Test messages have [TEST] in the
subject and explicitly identify themselves as development mail. Use an honest
test sender name for a personal Gmail mailbox, not an apparent official bank
sender. Localhost/private-IP, non-HTTPS and credential-bearing application links
are omitted from notifications because recipients cannot safely use them.
Configure a real, reachable public HTTPS FRONTEND_URL when deployed.

SMTP acceptance does not guarantee inbox placement. If Zoho classifies a message
as spam, the recipient should review its spam reason/headers and mark legitimate
mail as Not Spam. The bank's email administrator can inspect delivery logs and
quarantine. Do not disable SPF/DKIM/DMARC checks or trust all gmail.com senders.
For production, use a bank-authorized sender and configure the chosen provider's
SPF, DKIM and DMARC alignment with the bank's DNS/mail administrator. Merely
changing From to a bank address without authorization is not a fix. This code
does not modify DNS, spam policies, provider grants, or mailbox allowlists.

Requester creates an expense ticket with automatic requester identity, date,
purpose, department, particulars, quantities, unit costs, server-calculated totals
in naira, and optional titled evidence. One approver approves, returns, or rejects.
Approved tickets can be printed with approval details. Admin manages accounts
without workflow approval powers.

## User-facing failures and notifications

Notifications appear at the bottom right, can be dismissed, and reuse the same
toast for identical messages. Failed actions stay failed; nothing is silently
reported as successful. Validation explains what to correct, while server errors,
URLs, stack traces, SQL text and arbitrary exception messages are not echoed in
the UI. Unexpected API failures return generic JSON even in local DEBUG mode;
the backend retains diagnostics and preserves transaction rollback behavior.

Temporary connection failures preserve saved login tokens and offer retry.
Rejected/expired refresh tokens sign users out. Session termination clears the
query cache. Queries retry transient failures once; mutations are not retried
automatically, avoiding accidental duplicate submissions after timeouts.
Unexpected rendering errors show a refresh/help screen instead of a blank page.

Verify frontend failure handling without any live requests or email sending:

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\frontend
npm test
npm run build
```

Browser developer tools may still show HTTP failures and development diagnostics;
those are not user-facing notifications and are not suppressed to mask failures.

## Approval signatures and final downloads

In the sidebar, expand Settings to change your password. Approvers also have a
Signature submenu where they can upload a PNG or JPEG image (up to 1 MB and
2000 x 1000 pixels). Adding, replacing, or removing it requires their current
password. This is a visual signature, not a cryptographic digital signature.

Each new approval saves a private copy of the approver's signature on the
expense. Later signature changes do not affect existing approvals. Approvals
made before a signature was uploaded remain unsigned; they are not backfilled.
Every role can download approved expenses that it is already authorized to see,
using Download beside the status in Expenses or on the expense detail page.
Print / Save PDF is also available on the detail page.

For existing installations after pulling these changes:
```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```
Restart the backend and refresh the frontend. Admin's Users sidebar expands
into Manage users and Expense categories.
