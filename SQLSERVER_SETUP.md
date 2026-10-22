# Homebase Expenses: Microsoft SQL Server

## Current local setup

- Database: `homebase_expenses_mssql` on the local default SQL Server instance.
- Django backend adapter: `mssql-django==2.0.0`, compatible with this project's Django 6.1.
- Python driver: `mssql_python` (installed with the adapter, including its native driver).
- Authentication: the Windows identity running the backend. No new application login/password was created.
- Connection: `lpc:localhost` uses shared memory locally; SQL Server TCP does not have to be enabled or exposed.
- Frontend and backend URLs remain `http://127.0.0.1:5174` and `http://127.0.0.1:8001`.
- The active configuration is `backend/.env`. Copying a root example does not configure a running backend.

Only organizations, users/groups and categories were transferred. Password hashes,
roles and saved signature images were verified unchanged. Tickets, items, comments,
invoice records, history and number sequences were not imported into SQL Server.
The new database will generate its first new reference with sequence 0001 for the current year.
Shared SMTP settings and Django's secret remain in the existing .env, not in the database.

## Run from VS Code / PowerShell

Start SQL Server's `MSSQLSERVER` Windows service if it is stopped. You do not need
Docker Compose or the old PostgreSQL server for the current configuration.

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

In another terminal:

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\frontend
npm run dev
```

Do not start a second server if the relevant port already has the correct process.
Existing application passwords are unchanged; do not seed over preserved users.

## Recreating on a different development computer

Install a supported SQL Server version and Python, then create an empty database
named `homebase_expenses_mssql` in SSMS. This migration used
`Latin1_General_100_CS_AS_SC` collation to retain case-sensitive text semantics.
The Windows identity running Django needs access to that database and schema
creation permissions for migrations. For a genuinely empty installation only,
run `seed_demo` after migrations; new passwords print once and are sensitive.

Copy backend/.env.example to backend/.env and fill a new Django secret. The local
example permits the self-signed server certificate only for trusted local development.
Remote/production SQL should use a properly validated certificate, dedicated
least-privilege credentials and bank-approved infrastructure. Never enable a public
SQL Server port or run the application with a production sysadmin login.

## SQL Server-specific integrity safeguards

SQL Server does not support the expression indexes used by the model definitions
for lowercase category names and retired connected-mailbox emails. Two vendor-only
migrations add persisted lowercase computed columns and physical unique indexes.
They are no-ops on PostgreSQL/SQLite. Existing conditional uniqueness still enforces
one active approver per organization using a filtered index.

Django may emit `models.W044` for the original expression declarations on SQL Server.
The corresponding physical indexes are supplied by accounts migration 0011 and
expenses migration 0012; do not broadly silence future index warnings or remove
these migrations. Tests must verify direct database duplicate rejection, not only
serializer validation. Coordinate later changes to these constraints with their
vendor-specific migration implementation.

## Tests

```powershell
cd C:\Users\HP\Desktop\HomebaseExpenses\backend
.\.venv\Scripts\python.exe -m pytest -q
```

The test runner creates a separate `test_homebase_expenses_mssql` database; its
Windows account needs permission to create/drop that disposable database. It does
not clear the application's database. Email uses the in-memory backend under pytest.
SQLite-only smoke tests are available with `--ds=config.test_settings`, but cannot
prove SQL Server locking, computed indexes or filtered-index behavior.

## Cleanup and rollback

Before cleanup a custom PostgreSQL dump was created and checked with pg_restore.
Private recovery material is under backend/.backups/before-ticket-cleanup-20261020T121400Z/.
It contains sensitive data and is ignored by Git. Two tickets and related history
were removed from the old Homebase PostgreSQL database; six users, three categories
and one organization remained. Unrelated Workflow and mortgage-loan projects were untouched.

The obsolete dedicated PostgreSQL server was stopped and its backend/.postgres-data
directory removed after verifying the recovery dump checksum. The shared PostgreSQL
installation and unrelated projects were not removed. PostgreSQL is not needed to run
Homebase Expenses now.

Rollback is a restore operation, not merely an environment change: provision a new
dedicated PostgreSQL database, restore the private dump with pg_restore, configure its
credentials, set `DB_ENGINE=django.db.backends.postgresql`, apply pending migrations
and verify the data before restarting Homebase. The pre-cleanup dump contains the old
test tickets. Do not paste backups or saved .env contents into chat or Git. New SQL
Server writes are not in that dump and must be reconciled deliberately before rollback.

The previously generated PDF textbook describes the pre-SQL Server database setup;
use this document instead for database installation and startup.
