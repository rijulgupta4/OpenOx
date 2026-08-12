from pathlib import Path
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
table_dir = project_root / "outputs" / "tables"
figure_dir = project_root / "outputs" / "figures"
figure_dir.mkdir(parents=True, exist_ok=True)

summary = pd.read_csv(table_dir / "pairing_window_sensitivity_summary.csv")
incremental = pd.read_csv(table_dir / "pairing_window_incremental_summary.csv")

BLUE = "#2E74B5"
DARK_BLUE = "#0B2545"
LIGHT_BLUE = "#A9C7E8"
GOLD = "#B8860B"
GRAY = "#667085"
GRID = "#E5E7EB"
BLACK = "#101828"
WHITE = "#FFFFFF"

FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def centered(draw, xy, text, text_font, fill=BLACK):
    box = draw.textbbox((0, 0), text, font=text_font)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1]), text, font=text_font, fill=fill)


def draw_bar_panel(draw, bounds, labels, values, colors, title, y_label, formatter, headroom=1.18):
    left, top, right, bottom = bounds
    plot_left, plot_top = left + 130, top + 80
    plot_right, plot_bottom = right - 35, bottom - 100
    maximum = max(values) * headroom
    for step in range(5):
        value = maximum * step / 4
        y = plot_bottom - (plot_bottom - plot_top) * step / 4
        draw.line((plot_left, y, plot_right, y), fill=GRID, width=2)
        label = formatter(value)
        box = draw.textbbox((0, 0), label, font=font(22))
        draw.text((plot_left - 18 - (box[2] - box[0]), y - 12), label, font=font(22), fill=GRAY)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=BLACK, width=2)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=BLACK, width=2)
    draw.text((left + 15, top + 10), title, font=font(30, True), fill=DARK_BLUE)
    draw.text((left + 15, top + 48), y_label, font=font(20), fill=GRAY)

    width = (plot_right - plot_left) / len(values)
    bar_width = width * .52
    for index, (label, value, color) in enumerate(zip(labels, values, colors)):
        center = plot_left + width * (index + .5)
        height = (plot_bottom - plot_top) * value / maximum
        x0, x1 = center - bar_width / 2, center + bar_width / 2
        y0 = plot_bottom - height
        draw.rectangle((x0, y0, x1, plot_bottom), fill=color, outline=DARK_BLUE, width=2)
        centered(draw, (center, y0 - 36), formatter(value), font(24, True), DARK_BLUE)
        centered(draw, (center, plot_bottom + 18), str(label), font(23), BLACK)


retention = Image.new("RGB", (1400, 800), WHITE)
draw = ImageDraw.Draw(retention)
draw_bar_panel(
    draw, (30, 30, 1370, 720),
    summary["window_seconds"].astype(int).astype(str).tolist(),
    summary["paired_rows"].tolist(),
    [LIGHT_BLUE, BLUE, DARK_BLUE],
    "Paired observations retained by timestamp window",
    "Maximum blood-gas-to-marker gap (seconds)",
    lambda value: f"{int(round(value)):,}",
)
draw.text((150, 735), "Same 123 participants, 325 encounters, and 81 device labels in every cohort.", font=font(21), fill=GRAY)
retention.save(figure_dir / "pairing_window_retention.png", quality=95)

increment_plot = Image.new("RGB", (1800, 800), WHITE)
draw = ImageDraw.Draw(increment_plot)
colors = [LIGHT_BLUE, BLUE, GOLD]
draw_bar_panel(
    draw, (20, 20, 890, 760),
    incremental["gap_band_seconds"].tolist(), incremental["paired_rows"].tolist(), colors,
    "Rows contributed by gap band", "Absolute timestamp gap (seconds)",
    lambda value: f"{int(round(value)):,}",
)
draw_bar_panel(
    draw, (910, 20, 1780, 760),
    incremental["gap_band_seconds"].tolist(), incremental["mean_error_bias"].tolist(), colors,
    "Mean error within each added gap band", "SpO2 - SaO2 (percentage points)",
    lambda value: f"{value:.2f}",
    headroom=1.28,
)
increment_plot.save(figure_dir / "pairing_window_incremental_bands.png", quality=95)

print("Pairing-window figures written successfully with Pillow.")
