import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
TOKEN_USAGE_FILE = TMP_DIR / "token_usage.json"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return re.sub(r"^-+|-+$", "", text)


def log(message: str, style: str = "bold cyan") -> None:
    console.print(f"[{style}]{message}[/{style}]")


def log_error(message: str) -> None:
    console.print(f"[bold red]ERROR:[/bold red] {message}")


def log_success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def log_warning(message: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def track_tokens(model: str, input_tokens: int, output_tokens: int, stage: str) -> None:
    cost_per_million = {
        "sonar-pro": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
        "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    }
    rates = cost_per_million.get(model, {"input": 1.0, "output": 5.0})
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "stage": stage,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
    }

    TMP_DIR.mkdir(exist_ok=True)
    existing = []
    if TOKEN_USAGE_FILE.exists():
        with open(TOKEN_USAGE_FILE) as f:
            existing = json.load(f)
    existing.append(entry)
    with open(TOKEN_USAGE_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def is_cache_fresh(path: Path, max_age_seconds: int = 86400) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < max_age_seconds
