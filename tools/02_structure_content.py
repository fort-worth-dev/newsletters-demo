#!/usr/bin/env python3
"""Convert raw research JSON into newsletter schema JSON using claude-haiku."""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from utils import TMP_DIR, log, log_error, log_success, log_warning, slugify, track_tokens

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 2

NEWSLETTER_SCHEMA = {
    "headline": "string — punchy, specific headline",
    "subheadline": "string — one sentence expanding on the headline",
    "sections": [
        {
            "title": "string — section heading",
            "body": "string — 2-3 paragraphs of prose",
            "stat_callout": "string or null — one key stat highlighted in this section (e.g. '73% of firms...')",
        }
    ],
    "key_insight": "string — the single most important takeaway, 1-2 sentences",
    "key_stats": [{"label": "string", "value": "number", "unit": "string"}],
    "cta": "string — call to action closing the newsletter",
}

SYSTEM_PROMPT = f"""You are a newsletter editor. Convert raw research into a structured newsletter.
Return ONLY valid JSON matching this exact schema (no markdown, no extra keys):
{json.dumps(NEWSLETTER_SCHEMA, indent=2)}

Rules:
- sections: exactly 3 sections
- key_stats: 3-5 items, value MUST be a number (not a string like "73%")
- All strings must be complete sentences or phrases, no placeholder text
- Tone: professional, direct, informative — not hype-y"""


def structure_content(research_file: Path) -> dict:
    with open(research_file) as f:
        research = json.load(f)

    slug = research["slug"]
    output_path = TMP_DIR / f"content_{slug}.json"

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log_error("ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Topic: {research['topic']}

Summary:
{research.get('summary', '')}

Key facts:
{json.dumps(research.get('key_facts', []), indent=2)}

Key stats from research:
{json.dumps(research.get('key_stats', []), indent=2)}

Citations available: {len(research.get('citations', []))}

Structure this into a newsletter. Return only the JSON object."""

    result = None
    for attempt in range(1, MAX_RETRIES + 1):
        log(f"Structuring content (attempt {attempt}/{MAX_RETRIES})...")
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        track_tokens(
            MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
            "02_structure_content",
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            result = json.loads(raw)
            _validate_schema(result)
            break
        except (json.JSONDecodeError, ValueError) as e:
            log_warning(f"Attempt {attempt} failed validation: {e}")
            if attempt == MAX_RETRIES:
                log_error("Max retries reached. Could not get valid JSON from Claude.")
                sys.exit(1)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    log_success(f"Content structured and saved to {output_path}")
    return result


def _validate_schema(data: dict) -> None:
    required = ["headline", "subheadline", "sections", "key_insight", "key_stats", "cta"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required key: {key}")

    if not isinstance(data["sections"], list) or len(data["sections"]) == 0:
        raise ValueError("sections must be a non-empty list")

    for stat in data.get("key_stats", []):
        if not isinstance(stat.get("value"), (int, float)):
            raise ValueError(f"key_stats value must be numeric, got: {stat.get('value')!r}")


def main():
    parser = argparse.ArgumentParser(description="Structure research into newsletter content")
    parser.add_argument("--research-file", required=True, help="Path to .tmp/research_{slug}.json")
    args = parser.parse_args()

    research_file = Path(args.research_file)
    if not research_file.exists():
        log_error(f"Research file not found: {research_file}")
        sys.exit(1)

    result = structure_content(research_file)
    log_success(f"Headline: {result['headline']}")


if __name__ == "__main__":
    main()
