#!/usr/bin/env python3
"""Render newsletter HTML from content JSON and chart images."""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from premailer import transform

sys.path.insert(0, str(Path(__file__).parent))
from utils import TMP_DIR, log, log_error, log_success, log_warning

TEMPLATES_DIR = Path(__file__).parent / "templates"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _b64_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def render(content_file: Path, charts_dir: Path | None = None) -> Path:
    with open(content_file) as f:
        content = json.load(f)

    slug = content.get("slug") or content_file.stem.replace("content_", "")
    date_str = datetime.now().strftime("%B %d, %Y")
    output_path = TMP_DIR / f"newsletter_{slug}_{datetime.now().strftime('%Y%m%d')}.html"

    # Resolve charts directory
    if charts_dir is None:
        charts_dir = TMP_DIR / f"charts_{slug}"

    bar_chart_b64 = ""
    stat_cards_b64 = []

    if charts_dir.exists():
        bar_path = charts_dir / "chart_bar.png"
        if bar_path.exists():
            bar_chart_b64 = _b64_image(bar_path)
        else:
            log_warning("Bar chart not found — skipping.")

        for i in range(1, 10):
            card_path = charts_dir / f"chart_stat_{i}.png"
            if card_path.exists():
                stat_cards_b64.append(_b64_image(card_path))
            else:
                break
    else:
        log_warning(f"Charts directory not found: {charts_dir} — rendering without charts.")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("newsletter.html.j2")

    html = template.render(
        headline=content["headline"],
        subheadline=content["subheadline"],
        sections=content["sections"],
        key_insight=content["key_insight"],
        key_stats=content.get("key_stats", []),
        cta=content["cta"],
        date=date_str,
        bar_chart_b64=bar_chart_b64,
        stat_cards_b64=stat_cards_b64,
    )

    # Inline all CSS for email client compatibility
    html = transform(html, base_url=None, remove_classes=False)

    TMP_DIR.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = output_path.stat().st_size / 1024
    log_success(f"Newsletter rendered → {output_path} ({size_kb:.1f} KB)")

    if size_kb > 100:
        log_warning(
            f"HTML is {size_kb:.1f} KB — Gmail clips at ~102 KB. "
            "Consider reducing chart image sizes."
        )

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Render newsletter HTML")
    parser.add_argument("--content-file", help="Path to .tmp/content_{slug}.json")
    parser.add_argument("--charts-dir", help="Path to .tmp/charts_{slug}/ directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use fixture data (no API cost) for template development",
    )
    args = parser.parse_args()

    if args.dry_run:
        content_file = FIXTURES_DIR / "sample_content.json"
        charts_dir = None
        log("DRY RUN — using fixture data, no charts.", style="bold yellow")
    else:
        if not args.content_file:
            log_error("--content-file is required (or use --dry-run)")
            sys.exit(1)
        content_file = Path(args.content_file)
        if not content_file.exists():
            log_error(f"Content file not found: {content_file}")
            sys.exit(1)
        charts_dir = Path(args.charts_dir) if args.charts_dir else None

    output = render(content_file, charts_dir)
    log(f"Open in browser: file://{output}", style="dim")


if __name__ == "__main__":
    main()
