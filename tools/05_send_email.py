#!/usr/bin/env python3
"""Send the rendered newsletter HTML via Resend API."""

import argparse
import os
import sys
from pathlib import Path

import resend
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from utils import log, log_error, log_success

load_dotenv(override=True)

DEFAULT_FROM = "Newsletter <onboarding@resend.dev>"  # update once you have a verified domain


def send_email(html_file: Path, to: str, subject: str | None = None) -> str:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        log_error("RESEND_API_KEY not set in .env")
        sys.exit(1)

    resend.api_key = api_key

    with open(html_file, encoding="utf-8") as f:
        html_content = f.read()

    if subject is None:
        # Derive subject from filename: newsletter_ai_agents_20250515.html → "Newsletter: Ai Agents"
        stem = html_file.stem  # newsletter_ai_agents_20250515
        parts = stem.split("_")[1:-1]  # drop 'newsletter' prefix and date suffix
        subject = "Newsletter: " + " ".join(p.capitalize() for p in parts)

    from_address = os.getenv("RESEND_FROM", DEFAULT_FROM)

    log(f"Sending to {to} via Resend...")
    log(f"Subject: {subject}", style="dim")

    params: resend.Emails.SendParams = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "html": html_content,
    }

    response = resend.Emails.send(params)
    message_id = response.get("id", "unknown")

    log_success(f"Email sent! Resend message ID: {message_id}")
    return message_id


def main():
    parser = argparse.ArgumentParser(description="Send newsletter via Resend API")
    parser.add_argument("--html-file", required=True, help="Path to rendered newsletter HTML")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", help="Email subject line (auto-derived from filename if omitted)")
    args = parser.parse_args()

    html_file = Path(args.html_file)
    if not html_file.exists():
        log_error(f"HTML file not found: {html_file}")
        sys.exit(1)

    send_email(html_file, to=args.to, subject=args.subject)


if __name__ == "__main__":
    main()
