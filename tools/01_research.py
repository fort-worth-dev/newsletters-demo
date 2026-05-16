#!/usr/bin/env python3
"""Research a topic via Perplexity sonar-pro. Results cached for 24 hours."""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from utils import TMP_DIR, is_cache_fresh, log, log_error, log_success, log_warning, slugify, track_tokens

load_dotenv()

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar-pro"

SYSTEM_PROMPT = """You are a research analyst producing content for a professional newsletter.
Given a topic, return a JSON object with these exact keys:
- summary: 3-4 paragraph prose overview of the topic (current state, trends, significance)
- key_facts: list of 5-7 specific, concrete facts with numbers/dates where possible
- key_stats: list of 3-5 statistics, each as {label, value, unit} where value is a number
- citations: will be populated from API response separately

Return ONLY valid JSON, no markdown fences, no extra text."""


def research(topic: str, force: bool = False) -> dict:
    slug = slugify(topic)
    output_path = TMP_DIR / f"research_{slug}.json"
    TMP_DIR.mkdir(exist_ok=True)

    if not force and is_cache_fresh(output_path):
        log_warning(f"Using cached research for '{topic}' (< 24h old). Use --force to refresh.")
        with open(output_path) as f:
            return json.load(f)

    log(f"Researching: {topic}")
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        log_error("PERPLEXITY_API_KEY not set in .env")
        sys.exit(1)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research this topic for a newsletter: {topic}"},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }

    resp = requests.post(
        PERPLEXITY_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    content_str = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    track_tokens(MODEL, input_tokens, output_tokens, "01_research")

    try:
        result = json.loads(content_str)
    except json.JSONDecodeError as e:
        log_error(f"Perplexity returned invalid JSON: {e}")
        log_error(f"Raw content: {content_str[:500]}")
        sys.exit(1)

    result["citations"] = citations
    result["topic"] = topic
    result["slug"] = slug

    if not citations:
        log_warning("No citations returned — consider refining the topic for better sourcing.")

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    log_success(f"Research saved to {output_path}")
    if citations:
        log(f"Citations ({len(citations)}):", style="dim")
        for i, url in enumerate(citations, 1):
            log(f"  {i}. {url}", style="dim")

    return result


def main():
    parser = argparse.ArgumentParser(description="Research a topic via Perplexity sonar-pro")
    parser.add_argument("--topic", required=True, help="Newsletter topic to research")
    parser.add_argument("--force", action="store_true", help="Bypass 24h cache and re-fetch")
    args = parser.parse_args()

    result = research(args.topic, force=args.force)
    log_success(f"Done. key_stats found: {len(result.get('key_stats', []))}")


if __name__ == "__main__":
    main()
