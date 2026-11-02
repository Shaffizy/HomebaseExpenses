# Three-stage expense workflow release

Requester -> Awaiting review -> Awaiting approval -> Approved.
Reviewer-created expenses go straight to Awaiting approval. Reviewers cannot act on their own requests. Review and approval can return (with a comment) or reject (with a comment). Returned requests go back to their creator; requester resubmissions repeat review. Existing requests already awaiting approval remain there. No existing users, expenses or history are deleted.

With multiple reviewers, requester submissions are assigned to the first active reviewer in the requester's department by account ID. Admins assign departments in User management; requesters cannot select another department. Existing accounts remain unassigned until an administrator configures them. Only the assigned reviewer can act. Configure an active reviewer before reopening submissions. Reviewer accounts can create their own expenses and view their assigned reviews. Review completion records the reviewer and date in history.

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

## Department routing update (2026-11-02)

Back up the database and stop HB-expenses-api before deploying. Pull the release, run manage.py migrate as the authorized deployment account, rebuild frontend with npm ci then npm run build, and restart HB-expenses-api. This release adds accounts.0013_user_department; it does not guess departments or delete any records. Source changes require the usual service read permissions and IIS dist read permissions.

Before users submit, sign in as admin and assign the correct department to each requester and reviewer under User management -> Edit. The approver remains organization-wide. Department choices match the existing expense departments. If an account has no department or its department has no active reviewer, submission is blocked with a clear message. Reviewer-created expenses still go directly to the approver.

For existing pending reviews, after department assignments are complete, preview routing using the deployment account in backend:

```powershell
.\.venv314_new\Scripts\python.exe manage.py reroute_department_reviews
```

Review the reported missing reviewer IDs, configure their departments/reviewers, then apply:

```powershell
.\.venv314_new\Scripts\python.exe manage.py reroute_department_reviews --apply
```

Preview does not write or send email. Apply changes only pending reviewer assignments, records history, and sends notifications for changed assignments. If any pending expense lacks a valid department reviewer, no assignments are changed. Other statuses and the expense department stay unchanged. Existing drafts from another department must be edited by their owner to adopt the owner's configured department before submission.

## Category selector restoration (2026-11-02)

The expense form again shows a Category dropdown alongside the custom Expense name. Options come from active categories managed in Admin -> Categories, without hardcoded replacement names. Category is separate from department routing. Existing inactive categories are retained when editing an expense without changing its category. No database migration is needed for this release.

On the server: pull the release, run npm ci and npm run build in frontend, retain IIS read access to dist, then restart only HB-expenses-api to load the additional category display field. Refresh the browser with Ctrl+F5. If the dropdown has no options, an administrator must configure active categories in Categories. Cash advance is a future separate change and is not implemented here.

## Category and Particular form simplification

Expense name is no longer shown or required in the form. Category is required in the new frontend and supplies the saved summary automatically. The legacy title field is retained for history and older clients; no migration or data deletion is required. Selecting a category fills the first Particular when blank, or replaces its previous automatic category text. Custom particulars are not overwritten. Clearing Particular does not refill it until another category is selected. Each Particular remains editable and must contain a description before saving. Deploy by pulling the release, rebuilding frontend and restarting only HB-expenses-api.
