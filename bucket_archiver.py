#!/usr/bin/env python3
import argparse, re, sys, time
from typing import Dict, Tuple, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/drive"]
BUCKET_RE = re.compile(r"^Q(\d{6,7})")

def log(verbose, *a):
    if verbose:
        print(*a)

def get_service(client_secrets_path: str, token_path: str):
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except Exception:
        creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)

def bucket_range(n: int) -> Tuple[int, int]:
    base = (n // 1000) * 1000
    return base, base + 999

def bucket_name_for(n: int) -> str:
    low, high = bucket_range(n)
    return f"Q{low:06d}-Q{high:06d}"

def parse_q_number(name: str):
    m = BUCKET_RE.match(name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

def list_child_folders(drive, parent_id: str, drive_id: Optional[str], verbose=False):
    page_token = None
    seen = 0
    while True:
        params = {
            "q": f"mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false",
            "pageSize": 200,
            "pageToken": page_token,
            "fields": "nextPageToken, files(id, name, parents)",
            "supportsAllDrives": True,
        }
        if drive_id:
            params.update({
                "corpora": "drive",
                "driveId": drive_id,
                "includeItemsFromAllDrives": True,
            })
        else:
            params.update({"corpora": "user"})
        res = drive.files().list(**params).execute()
        files = res.get("files", [])
        for f in files:
            seen += 1
            yield f
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    log(verbose, f"[list_child_folders] parent={parent_id} corpora={'drive' if drive_id else 'user'} count={seen}")

def find_or_create_folder(drive, name: str, parent_id: str, drive_id: Optional[str], verbose=False) -> str:
    safe_name = name.replace("'", "\\'")
    q = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    params = {
        "q": q,
        "fields": "files(id, name)",
        "supportsAllDrives": True,
    }
    if drive_id:
        params.update({
            "corpora": "drive",
            "driveId": drive_id,
            "includeItemsFromAllDrives": True,
        })
    else:
        params.update({"corpora": "user"})
    res = drive.files().list(**params).execute()
    files = res.get("files", [])
    if files:
        log(verbose, f"[bucket exists] {name} -> {files[0]['id']}")
        return files[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    f = drive.files().create(body=body, supportsAllDrives=True, fields="id").execute()
    log(verbose, f"[bucket created] {name} -> {f['id']}")
    return f["id"]

def move_folder(drive, file_id: str, old_parent_id: str, new_parent_id: str, verbose=False):
    for attempt in range(5):
        try:
            drive.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parent_id,
                supportsAllDrives=True,
                fields="id, parents",
            ).execute()
            log(verbose, f"[moved] {file_id}  {old_parent_id} -> {new_parent_id}")
            return
        except HttpError as e:
            status = getattr(e, "resp", None).status if getattr(e, "resp", None) else None
            log(verbose, f"[retryable error] status={status} attempt={attempt+1} file={file_id}")
            if status in (403, 429, 500, 503):
                time.sleep((2 ** attempt) + 0.25)
                continue
            raise

def build_bucket_map(drive, bucket_parent_id: str, drive_id: Optional[str], verbose=False) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for f in list_child_folders(drive, bucket_parent_id, drive_id, verbose):
        if re.match(r"^Q\d{6}-Q\d{6}$", f["name"]):
            m[f["name"]] = f["id"]
            continue
        n = parse_q_number(f["name"])
        if n is None:
            continue
        bname = bucket_name_for(n)
        if f["name"] == bname:
            m[f["name"]] = f["id"]
    log(verbose, f"[bucket_map] {len(m)} existing buckets cached")
    return m

def main():
    ap = argparse.ArgumentParser(description="Bucket archived folders (Q######-Name) into 1,000-range folders in a Shared Drive or My Drive.")
    ap.add_argument("--client-secrets", default="client_secret.json")
    ap.add_argument("--token", default="token.json")
    ap.add_argument("--drive-id", help="ID of the Shared Drive (omit for My Drive)")
    ap.add_argument("--source-parent-id", required=True, help="Folder ID to scan for Q-folders.")
    ap.add_argument("--bucket-parent-id", required=True, help="Folder ID under which bucket folders should be created.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prefix", default="Q")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    global BUCKET_RE
    BUCKET_RE = re.compile(rf"^{re.escape(args.prefix)}(\d{{6,7}})")

    drive = get_service(args.client_secrets, args.token)

    bucket_cache = build_bucket_map(drive, args.bucket_parent_id, args.drive_id, args.verbose)

    planned = []
    for f in list_child_folders(drive, args.source_parent_id, args.drive_id, args.verbose):
        name = f["name"]
        n = parse_q_number(name)
        log(args.verbose, f"[scan] {name} -> qnum={n}")
        if n is None:
            continue
        bname = bucket_name_for(n)
        bucket_id = bucket_cache.get(bname)
        if not bucket_id:
            bucket_id = find_or_create_folder(drive, bname, args.bucket_parent_id, args.drive_id, args.verbose)
            bucket_cache[bname] = bucket_id
        parents = f.get("parents") or []
        old_parent = parents[0] if parents else args.source_parent_id
        if bucket_id in parents:
            log(args.verbose, f"[skip] already in correct bucket: {name}")
            continue
        planned.append((f["id"], name, old_parent, bucket_id, bname))

    if not planned:
        print("No moves needed.")
        return

    print(f"Planned moves: {len(planned)}")
    for _, name, _, _, bname in planned:
        print(f"  {name}  ->  {bname}")

    if args.dry_run:
        print("Dry-run: no changes made.")
        return

    moved = 0
    for file_id, name, old_parent, new_parent, bname in planned:
        move_folder(drive, file_id, old_parent, new_parent, args.verbose)
        moved += 1
        print(f"Moved: {name} -> {bname}")
    print(f"Done. Moved {moved} folders.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
