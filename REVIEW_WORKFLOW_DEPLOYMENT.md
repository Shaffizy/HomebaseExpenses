# Three-stage expense workflow release

Requester -> Awaiting review -> Awaiting approval -> Approved.
Reviewer-created expenses go straight to Awaiting approval. Reviewers cannot act on their own requests. Review and approval can return (with a comment) or reject (with a comment). Returned requests go back to their creator; requester resubmissions repeat review. Existing requests already awaiting approval remain there. No existing users, expenses or history are deleted.

With multiple reviewers, requester submissions are assigned to the first active reviewer by account ID. Only the assigned reviewer can act. Configure an active reviewer before reopening submissions. Reviewer accounts can create their own expenses and view their assigned reviews. Review completion records the reviewer and date in history.

Admin: User management -> Edit allows changing username and optionally setting a new password. Blank password preserves the current one. Passwords are validated, hashed and never returned by the API. Password changes invalidate previous JWT credentials under the existing password-aware token configuration. Tell the user their new login name privately.

## Server rollout

Back up HomebaseExpenses in SSMS and preserve the server .env and private uploads. Deploy only this application's files. Stop HB-expenses-api for the migration and run the migration as the authorized Administrator identity, not the restricted runtime account:

```powershell
cd C:\Users\Administrator\HomebaseExpenses\backend
.\.venv314_new\Scripts\python.exe manage.py migrate
```

Build the frontend on the development PC with npm run build and copy the complete frontend/dist contents to the matching server folder. The source frontend/public/web.config now preserves the existing IIS -> nginx:8091 proxy during builds. Keep the site's existing binding on port 3005. Ensure the service retains read access to newly deployed backend files and IIS retains read access to dist.

Set these values privately in the server backend/.env:

```ini
EMAIL_TEST_MODE=False
FRONTEND_URL=http://10.10.5.133:3005
```

Use the reachable HTTPS URL instead when TLS is configured. The bank IP link works only inside the bank network/VPN and requires port 3005 connectivity. Links never grant access without sign-in. Loopback, credentials, queries, fragments, unsafe schemes and link-local addresses are rejected. Keep the approved SMTP sender and credentials in the server .env.

Restart only HB-expenses-api. Sign in as admin, configure a reviewer, and test requester -> reviewer -> approver and reviewer -> approver. Verify username changes and password resets on a dedicated authorized account. No real notification emails are sent by the automated tests. The admin's explicitly requested email-delivery test remains labelled as a test; real workflow notifications use production wording when EMAIL_TEST_MODE=False.
