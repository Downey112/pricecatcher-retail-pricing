"""Draw the README chart as SVG, in a light and a dark variant.

Standard library only. The chart shows the model's store-format coefficients with
their 95% confidence intervals, read against the supermarket baseline.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
COEFFICIENTS = ROOT / "data" / "processed" / "model_coefficients.csv"

FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
THEMES = {
    "light": {
        "surface": "#ffffff", "ink": "#1f2328", "secondary": "#59636e", "muted": "#818b98",
        "grid": "#d9dee3", "axis": "#b7bfc8", "series": "#2a78d6", "border": "#d1d9e0",
    },
    "dark": {
        "surface": "#0d1117", "ink": "#f0f6fc", "secondary": "#9198a1", "muted": "#7d8590",
        "grid": "#262c36", "axis": "#3d444d", "series": "#3987e5", "border": "#3d444d",
    },
}
BASELINE = "Supermarket"
ORDER = ["Hypermarket", BASELINE, "Mini market", "Sundry shop", "Wet market"]


def load():
    rows = {BASELINE: (0.0, 0.0, 0.0)}
    with open(COEFFICIENTS, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["factor"] == "format":
                rows[row["term"]] = (
                    float(row["premium_pct"]), float(row["ci_low_pct"]), float(row["ci_high_pct"])
                )
    return [(name, *rows[name]) for name in ORDER]


def signed(value):
    return f"{value:+.1f}%" if value else "baseline"


def chart(theme, rows):
    width, height = 880, 330
    left, right, top, row_height = 150, 760, 96, 40
    low, high = -5, 12

    def px(value):
        return left + (value - low) / (high - low) * (right - left)

    bottom = top + row_height * len(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" font-family="{FONT}" role="img">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{theme["surface"]}" stroke="{theme["border"]}"/>',
        f'<text x="28" y="38" font-size="17" font-weight="600" fill="{theme["ink"]}">'
        "Same item, same month, same state: the store format still moves the price</text>",
        f'<text x="28" y="60" font-size="12.5" fill="{theme["secondary"]}">'
        "Price premium over a supermarket for the same item in the same month and state, "
        "with 95% confidence interval</text>",
    ]

    for tick in range(low, high + 1, 5):
        x = px(tick)
        is_zero = tick == 0
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{bottom}" '
            f'stroke="{theme["axis"] if is_zero else theme["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 20}" font-size="11.5" text-anchor="middle" '
            f'fill="{theme["muted"]}">{tick:+d}%</text>' if tick else
            f'<text x="{x:.1f}" y="{bottom + 20}" font-size="11.5" text-anchor="middle" '
            f'fill="{theme["muted"]}">0</text>'
        )

    for index, (name, estimate, ci_low, ci_high) in enumerate(rows):
        y = top + row_height * index + row_height / 2
        is_baseline = name == BASELINE
        parts.append(
            f'<text x="{left - 16}" y="{y + 4:.1f}" font-size="13" text-anchor="end" '
            f'fill="{theme["ink"]}">{name}</text>'
        )
        if not is_baseline:
            parts.append(
                f'<line x1="{px(ci_low):.1f}" y1="{y:.1f}" x2="{px(ci_high):.1f}" y2="{y:.1f}" '
                f'stroke="{theme["series"]}" stroke-width="2" stroke-linecap="round"/>'
            )
        # The baseline is drawn hollow: it is the reference point, not an estimate
        parts.append(
            f'<circle cx="{px(estimate):.1f}" cy="{y:.1f}" r="5.5" '
            f'fill="{theme["surface"] if is_baseline else theme["series"]}" '
            f'stroke="{theme["muted"] if is_baseline else theme["surface"]}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{right + 16}" y="{y + 4:.1f}" font-size="13" font-weight="600" '
            f'fill="{theme["secondary"] if is_baseline else theme["ink"]}">{signed(estimate)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def build():
    ASSETS.mkdir(exist_ok=True)
    rows = load()
    for name, theme in THEMES.items():
        out_file = ASSETS / f"format-premium-{name}.svg"
        out_file.write_text(chart(theme, rows), encoding="utf-8")
        print(f"[OK] {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
