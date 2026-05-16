#!/usr/bin/env python3
"""Archive a rendered newsletter HTML to Google Sheets."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent))
from utils import log, log_error, log_success, log_warning

load_dotenv(override=True)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent.parent / "token.json"

HEADER_ROW = ["Date", "Slug", "Headline", "File Path", "Size (KB)", "Archived At"]


def _get_creds() -> Credentials:
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                log_error(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
        os.chmod(TOKEN_FILE, 0o600)

    return creds


def _ensure_header(service, spreadsheet_id: str, sheet_name: str) -> None:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:F1")
        .execute()
    )
    existing = result.get("values", [])
    if not existing or existing[0] != HEADER_ROW:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [HEADER_ROW]},
        ).execute()
        log("Header row written.", style="dim")


def _parse_archive_metadata(html_file: Path) -> tuple[str, str]:
    """Parse newsletter date and slug from a filename safely."""
    stem = html_file.stem
    parts = stem.split("_")
    today = datetime.now().strftime("%Y-%m-%d")

    if len(parts) < 3 or parts[0] != "newsletter":
        log_warning(
            f"Filename '{stem}' does not match expected pattern "
            "'newsletter_{{slug}}_{{YYYYMMDD}}'; using filename stem as slug and today as date."
        )
        return today, stem

    slug = "_".join(parts[1:-1]).strip("_")
    if not slug:
        log_warning(
            f"Filename '{stem}' does not contain a valid slug; "
            "using filename stem as slug and today as date."
        )
        return today, stem

    date_part = parts[-1]
    try:
        newsletter_date = datetime.strptime(date_part, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        newsletter_date = today
        log_warning(f"Could not parse date from filename '{stem}', using today.")

    return newsletter_date, slug


def archive(html_file: Path, spreadsheet_id: str, sheet_name: str = "Archive") -> str:
    if not html_file.exists():
        log_error(f"HTML file not found: {html_file}")
        sys.exit(1)

    newsletter_date, slug = _parse_archive_metadata(html_file)

    size_kb = round(html_file.stat().st_size / 1024, 1)
    archived_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Read headline from HTML (first <h1> tag) as a best-effort label
    html_content = html_file.read_text(encoding="utf-8")
    headline = slug.replace("_", " ").title()  # fallback
    import re
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
    if match:
        headline = re.sub(r"<[^>]+>", "", match.group(1)).strip()

    row = [newsletter_date, slug, headline, str(html_file.resolve()), size_kb, archived_at]

    log(f"Authenticating with Google Sheets...")
    creds = _get_creds()
    service = build("sheets", "v4", credentials=creds)

    _ensure_header(service, spreadsheet_id, sheet_name)

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    log_success(f"Archived '{slug}' → {sheet_url}")
    return sheet_url


def main():
    parser = argparse.ArgumentParser(description="Archive newsletter HTML to Google Sheets")
    parser.add_argument("--html-file", required=True, help="Path to rendered newsletter HTML")
    parser.add_argument(
        "--spreadsheet-id",
        default=os.getenv("SHEETS_ARCHIVE_ID"),
        help="Google Sheets spreadsheet ID (or set SHEETS_ARCHIVE_ID in .env)",
    )
    parser.add_argument(
        "--sheet-name",
        default="Archive",
        help="Tab name within the spreadsheet (default: Archive)",
    )
    args = parser.parse_args()

    if not args.spreadsheet_id:
        log_error(
            "--spreadsheet-id is required (or set SHEETS_ARCHIVE_ID in .env). "
            "Find the ID in the spreadsheet URL: /spreadsheets/d/<ID>/edit"
        )
        sys.exit(1)

    archive(Path(args.html_file), args.spreadsheet_id, args.sheet_name)


if __name__ == "__main__":
    main()
