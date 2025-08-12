Drive Bucket Archiver (Google Shared Drives)
Automatically bucket archived client folders (e.g., Q106404-Christopher) into 1,000-range folders like Q106000-Q106999, Q107000-Q107999, etc.
Great for MSPs dealing with weekly archive flows and needing clean, predictable organization.

Features
Detects folders named like Q######-Anything (default prefix Q).

Computes the correct 1,000-range bucket (e.g., 106404 → Q106000-Q106999).

Creates missing bucket folders automatically.

Moves matching folders into the correct bucket.

Dry-run mode to preview changes.

Works with Shared Drives (a.k.a. Team Drives).

Repo Layout
bash
Copy
Edit
drive_bucket_archiver/
├─ bucket_archiver.py      # main script
├─ requirements.txt        # dependencies
└─ .env.example            # reference only (do not use in prod)
Do not commit credentials:

bash
Copy
Edit
# .gitignore
client_secret.json
token.json
.env
Prereqs
Python 3.9+ (tested on macOS/Linux)

A Google account (Workspace not required)

Access to the Shared Drive or folders you want to reorganize
(Recommended role: Content manager or Manager)

Google API Setup (once)
Go to Google Cloud Console → Create a project.

Enable Google Drive API for that project.

Create OAuth client ID (Application type: Desktop app).

Download the credentials as client_secret.json into this repo folder.

First run will prompt a browser window to authorize and will create token.json locally.

Install
bash
Copy
Edit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Get Your IDs
Shared Drive ID (--drive-id): open the drive in the browser; URL contains drives/<DRIVE_ID>.

Source Parent ID (--source-parent-id): folder that currently holds your archived Q-folders.

Bucket Parent ID (--bucket-parent-id): folder under which the bucket folders (e.g., Q106000-Q106999) will be created.

Tip: Right-click folder → Get link → copy the long ID from the URL.

Usage
Dry Run (recommended)
bash
Copy
Edit
python bucket_archiver.py \
  --drive-id "<SHARED_DRIVE_ID>" \
  --source-parent-id "<ARCHIVE_SOURCE_FOLDER_ID>" \
  --bucket-parent-id "<BUCKETS_PARENT_FOLDER_ID>" \
  --dry-run
Example output:

yaml
Copy
Edit
Planned moves: 3
  Q106404-Christopher  ->  Q106000-Q106999
  Q107015-Amazon       ->  Q107000-Q107999
Dry-run: no changes made.
Execute
bash
Copy
Edit
python bucket_archiver.py \
  --drive-id "<SHARED_DRIVE_ID>" \
  --source-parent-id "<ARCHIVE_SOURCE_FOLDER_ID>" \
  --bucket-parent-id "<BUCKETS_PARENT_FOLDER_ID>"
Optional Flags
--client-secrets client_secret.json (default: client_secret.json)

--token token.json (default: token.json)

--prefix Q (change Q to another leading letter if needed)

Safe Test Scenario
Create a scratch area in your Shared Drive:

Folder A (source): add samples like
Q106404-Christopher, Q107015-Amazon, Q108999-Zappos, IgnoreMe

Folder B (bucket parent): empty

Run dry-run, confirm planned moves.

Run without --dry-run.

Verify bucket folders were created under Folder B and contents moved.

Automation (cron)
Run every Monday at 02:05:

bash
Copy
Edit
crontab -e
5 2 * * MON /full/path/.venv/bin/python /full/path/bucket_archiver.py \
  --drive-id "YOUR_DRIVE_ID" \
  --source-parent-id "ARCHIVE_SOURCE_FOLDER_ID" \
  --bucket-parent-id "BUCKETS_PARENT_FOLDER_ID" >> /full/path/archiver.log 2>&1
FAQ
Do I need Google Workspace?
No — a personal Google account works if it has the right permissions.

What permissions are required?
At least Content manager on the folders you’re modifying.

Will it rename my folders?
No — it only creates bucket folders and moves existing folders into them.

What naming patterns are supported?
Default regex is ^Q(\d{6,7}) (six digits expected, seven allowed). Use --prefix to change.

Rate limits or transient errors?
The script retries on 429/5xx Drive API errors with exponential backoff.

Contributing
Fork and create a feature branch.

Make changes.

Open a PR with a clear description and test notes
