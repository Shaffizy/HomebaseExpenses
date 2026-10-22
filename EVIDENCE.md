# Bill evidence

Choose evidence categories and files directly on the new-bill form before saving
or submitting. Save & submit creates the draft, uploads each selected document,
then submits only when every upload succeeds. A failed upload leaves a saved draft
and preserves selections for retry; completed uploads are not duplicated.
Existing draft/returned bills also support evidence on their detail page.
Categories: birth certificate, proof of identification, application letter,
statement of account, invoice/receipt, and Other (requires a custom document name).
Multiple documents may be attached, including multiple documents in one category.
Evidence is optional; no category is required to submit a bill.

PDF, PNG, and JPEG files are supported, up to 10 MB per file. File extensions
and signatures are checked. This is not malware scanning: add antivirus scanning
and a web-server request-size limit before deploying uploads to production.

Only the bill's creator, with BILLER role, can upload or remove evidence while
the bill is DRAFT or RETURNED. Authenticated users in the bill's organization
can list and download documents. Cross-organization requests return 404.
Files are downloaded through authenticated endpoints, never public media URLs.

Endpoints:
- GET/POST /api/bills/{id}/evidence/
- GET/DELETE /api/bills/{id}/evidence/{evidence_id}/

Uploads use multipart fields category, label, and file. The API returns document
metadata but never exposes storage paths. Category values are BIRTH_CERTIFICATE,
IDENTIFICATION, APPLICATION_LETTER, ACCOUNT_STATEMENT, INVOICE_RECEIPT, and OTHER.

Files live in backend/private_evidence by default. PRIVATE_EVIDENCE_ROOT can
override this directory. Keep it outside publicly served directories and include
it in secure backups. Deleting evidence or its parent bill deletes the stored file
after the database transaction commits.

PowerShell setup:
```powershell
cd C:\Users\HP\Desktop\Workflow\backend
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver
```

In a second terminal:
```powershell
cd C:\Users\HP\Desktop\Workflow\frontend
npm run dev
```

Verify: log in as a biller, save a draft, attach a PDF, download it as a reviewer,
then submit the bill and confirm upload/remove controls are no longer available.
