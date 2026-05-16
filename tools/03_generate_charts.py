#!/usr/bin/env python3
"""Generate matplotlib charts from key_stats in content JSON."""

import argparse
import json
import sys
from pathlib import Path

matplotlib_import_guard = True
import matplotlib
matplotlib.use("Agg")  # must be before any other matplotlib import (WSL2 has no display)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from utils import TMP_DIR, log, log_error, log_success, log_warning

# Newsletter color palette — used by both charts and Jinja2 template
PALETTE = {
    "primary": "#1A3C5E",       # deep navy
    "accent": "#2E86AB",        # teal blue
    "highlight": "#F6AE2D",     # amber
    "light_bg": "#F4F7FA",      # off-white
    "text": "#1C1C1C",
    "muted": "#6B7280",
    "bar_colors": ["#2E86AB", "#1A3C5E", "#F6AE2D", "#A23B72", "#3BB273"],
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": PALETTE["light_bg"],
    "figure.facecolor": "white",
    "axes.labelcolor": PALETTE["text"],
    "xtick.color": PALETTE["muted"],
    "ytick.color": PALETTE["muted"],
})


def generate_bar_chart(stats: list[dict], output_path: Path) -> None:
    labels = [s["label"][:40] + "…" if len(s["label"]) > 40 else s["label"] for s in stats]
    values = [float(s["value"]) for s in stats]
    units = [s.get("unit", "") for s in stats]

    fig, ax = plt.subplots(figsize=(6, max(2.5, len(labels) * 0.65)))
    bars = ax.barh(
        labels,
        values,
        color=PALETTE["bar_colors"][: len(labels)],
        height=0.55,
        edgecolor="none",
    )

    for bar, val, unit in zip(bars, values, units):
        label = f"{val:g}{unit}" if unit in ("%",) else f"{val:g} {unit}".strip()
        ax.text(
            bar.get_width() + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            ha="left",
            fontsize=10,
            color=PALETTE["text"],
            fontweight="bold",
        )

    ax.set_xlabel("")
    ax.set_xlim(0, max(values) * 1.18)
    ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_facecolor(PALETTE["light_bg"])

    plt.tight_layout(pad=1.2)
    plt.savefig(output_path, dpi=90, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def generate_stat_card(stat: dict, output_path: Path) -> None:
    """Single large-number stat card as a PNG image."""
    width, height = 520, 190
    img = Image.new("RGB", (width, height), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Background accent bar on left
    draw.rectangle([0, 0, 8, height], fill=PALETTE["accent"])

    # Card background
    draw.rectangle([8, 0, width, height], fill=PALETTE["light_bg"])

    value = stat["value"]
    unit = stat.get("unit", "")
    label = stat["label"]

    value_str = f"{value:g}{unit}" if unit in ("%",) else f"{value:g} {unit}".strip()

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        font_large = ImageFont.load_default()
        font_label = ImageFont.load_default()

    draw.text((40, 30), value_str, fill=PALETTE["primary"], font=font_large)
    draw.text((40, 160), label, fill=PALETTE["muted"], font=font_label)

    img.save(output_path, "PNG", optimize=True)


def generate_charts(content_file: Path) -> Path:
    with open(content_file) as f:
        content = json.load(f)

    slug = content.get("slug") or content_file.stem.replace("content_", "")
    charts_dir = TMP_DIR / f"charts_{slug}"
    charts_dir.mkdir(parents=True, exist_ok=True)

    key_stats = content.get("key_stats", [])
    if not key_stats:
        log_warning("No key_stats found in content JSON — skipping chart generation.")
        return charts_dir

    log(f"Generating charts for {len(key_stats)} stats...")

    # Bar chart combining all stats
    if len(key_stats) > 1:
        bar_path = charts_dir / "chart_bar.png"
        generate_bar_chart(key_stats, bar_path)
        log_success(f"Bar chart → {bar_path.name}")

    # Individual stat cards
    for i, stat in enumerate(key_stats[:3], 1):
        card_path = charts_dir / f"chart_stat_{i}.png"
        generate_stat_card(stat, card_path)
        log_success(f"Stat card {i} → {card_path.name}")

    log_success(f"Charts saved to {charts_dir}")
    return charts_dir


def main():
    parser = argparse.ArgumentParser(description="Generate charts from content JSON key_stats")
    parser.add_argument("--content-file", required=True, help="Path to .tmp/content_{slug}.json")
    args = parser.parse_args()

    content_file = Path(args.content_file)
    if not content_file.exists():
        log_error(f"Content file not found: {content_file}")
        sys.exit(1)

    generate_charts(content_file)


if __name__ == "__main__":
    main()
