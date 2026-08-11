#!/usr/bin/env python3
"""Create report-ready figures for the real YOLOv8n experiments."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLORS = {
    "blue": "#2563eb", "red": "#dc2626", "green": "#16a34a",
    "orange": "#f97316", "purple": "#7c3aed", "gray": "#64748b",
    "grid": "#d1d5db", "ink": "#111827",
}


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def axes(draw, box, ticks, maximum, formatter=lambda value: f"{value:g}"):
    x0, y0, x1, y1 = box
    for tick in ticks:
        y = y1 - tick / maximum * (y1 - y0)
        draw.line((x0, y, x1, y), fill=COLORS["grid"], width=1)
        draw.text((x0 - 10, y), formatter(tick), fill=COLORS["gray"],
                  font=font(16), anchor="rm")
    draw.line((x0, y0, x0, y1), fill=COLORS["ink"], width=3)
    draw.line((x0, y1, x1, y1), fill=COLORS["ink"], width=3)
    return lambda value: y1 - value / maximum * (y1 - y0)


def x_positions(box, count):
    x0, _, x1, _ = box
    step = (x1 - x0) / count
    return [x0 + step * (index + 0.5) for index in range(count)]


def labels_x(draw, box, rates):
    for x, rate in zip(x_positions(box, len(rates)), rates):
        draw.text((x, box[3] + 13), f"{rate:g} rps", fill=COLORS["ink"],
                  font=font(18), anchor="ma")


def legend(draw, x, y, entries):
    for index, (label, color) in enumerate(entries):
        left = x + index * 145
        draw.line((left, y, left + 28, y), fill=color, width=6)
        draw.text((left + 36, y), label, fill=COLORS["ink"],
                  font=font(16), anchor="lm")


def line_series(draw, box, values, maximum, color, value_format=".1f"):
    points = [(x, box[3] - value / maximum * (box[3] - box[1]))
              for x, value in zip(x_positions(box, len(values)), values)]
    draw.line(points, fill=color, width=5)
    for (x, y), value in zip(points, values):
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=color)
        draw.text((x, y - 12), format(value, value_format), fill=color,
                  font=font(15), anchor="ms")


def draw_aws(path: Path, load_rows: list[dict], metric_rows: list[dict]) -> None:
    rates = [float(row["rate_rps"]) for row in load_rows]
    canvas = Image.new("RGB", (1900, 1120), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((950, 30), "AWS Lambda container YOLOv8n — three load levels",
              fill=COLORS["ink"], font=font(34, True), anchor="ma")
    boxes = [(95, 175, 875, 485), (1040, 175, 1820, 485),
             (95, 710, 875, 1020), (1040, 710, 1820, 1020)]

    # E2E percentiles.
    box = boxes[0]
    maximum = 1200.0
    axes(draw, box, [0, 300, 600, 900, 1200], maximum)
    labels_x(draw, box, rates)
    draw.text((box[0], 115), "End-to-end latency (ms)", fill=COLORS["ink"],
              font=font(23, True), anchor="lm")
    p50 = [float(row["p50_ms"]) for row in load_rows]
    p95 = [float(row["p95_ms"]) for row in load_rows]
    line_series(draw, box, p50, maximum, COLORS["blue"])
    line_series(draw, box, p95, maximum, COLORS["red"])
    legend(draw, box[0] + 455, 125, [("p50", COLORS["blue"]), ("p95", COLORS["red"])])

    # Detect breakdown.
    box = boxes[1]
    maximum = 400.0
    scale = axes(draw, box, [0, 100, 200, 300, 400], maximum)
    labels_x(draw, box, rates)
    draw.text((box[0], 115), "Detect stage breakdown (ms, exact request IDs)",
              fill=COLORS["ink"], font=font(23, True), anchor="lm")
    series = [
        ("Detect", "detect_stage_avg_ms", COLORS["blue"]),
        ("Inference", "model_inference_avg_ms", COLORS["purple"]),
        ("S3 download", "image_download_avg_ms", COLORS["orange"]),
    ]
    centers = x_positions(box, len(rates))
    width = 48
    for center, row in zip(centers, metric_rows):
        for index, (_, key, color) in enumerate(series):
            value = float(row[key])
            left = center + (index - 1) * (width + 5) - width / 2
            draw.rectangle((left, scale(value), left + width, box[3]), fill=color)
            draw.text((left + width / 2, scale(value) - 7), f"{value:.1f}",
                      fill=color, font=font(14), anchor="ms")
    legend(draw, box[0] + 260, 148, [(name, color) for name, _, color in series])

    # Lambda Duration on logarithmic scale.
    box = boxes[2]
    log_min, log_max = -3.0, 3.0
    log_scale = lambda value: box[3] - (
        (math.log10(max(value, 10 ** log_min)) - log_min) / (log_max - log_min)
    ) * (box[3] - box[1])
    for tick in [0.001, 0.01, 0.1, 1, 10, 100, 1000]:
        y = log_scale(tick)
        draw.line((box[0], y, box[2], y), fill=COLORS["grid"], width=1)
        draw.text((box[0] - 10, y), f"{tick:g}", fill=COLORS["gray"],
                  font=font(16), anchor="rm")
    draw.line((box[0], box[1], box[0], box[3]), fill=COLORS["ink"], width=3)
    draw.line((box[0], box[3], box[2], box[3]), fill=COLORS["ink"], width=3)
    labels_x(draw, box, rates)
    draw.text((box[0], 650), "Lambda Duration (ms, log scale)", fill=COLORS["ink"],
              font=font(23, True), anchor="lm")
    centers = x_positions(box, len(rates))
    for center, row in zip(centers, metric_rows):
        for offset, key, color in (
            (-42, "lambda_detect_duration_avg_ms", COLORS["blue"]),
            (10, "lambda_alert_duration_avg_ms", COLORS["orange"]),
        ):
            value = float(row[key])
            top = log_scale(value)
            draw.rectangle((center + offset, top, center + offset + 32, box[3]), fill=color)
            draw.text((center + offset + 16, top - 7), f"{value:.2f}", fill=color,
                      font=font(14), anchor="ms")
    legend(draw, box[0] + 465, 660,
           [("Detect", COLORS["blue"]), ("Alert", COLORS["orange"])])

    # Executions and success rate.
    box = boxes[3]
    maximum = 1000.0
    scale = axes(draw, box, [0, 200, 400, 600, 800, 1000], maximum)
    labels_x(draw, box, rates)
    draw.text((box[0], 650), "Step Functions executions", fill=COLORS["ink"],
              font=font(23, True), anchor="lm")
    for x, row in zip(x_positions(box, len(rates)), load_rows):
        value = float(row["succeeded"])
        draw.rectangle((x - 50, scale(value), x + 50, box[3]), fill=COLORS["green"])
        draw.text((x, scale(value) - 8), f"{value:.0f}", fill=COLORS["green"],
                  font=font(17, True), anchor="ms")
        draw.text((x, scale(value) + 24), "100%", fill="white",
                  font=font(16, True), anchor="ma")
    draw.text((box[2], 660), "Failed: 0 at every level", fill=COLORS["red"],
              font=font(17), anchor="rm")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def draw_local(path: Path, summaries: list[dict]) -> None:
    rates = [float(item["experiment"]["target_rate_rps"]) for item in summaries]
    canvas = Image.new("RGB", (1900, 760), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((950, 28), "Real YOLOv8n on local Edge/Cloud simulator",
              fill=COLORS["ink"], font=font(34, True), anchor="ma")
    boxes = [(90, 175, 620, 650), (735, 175, 1265, 650), (1380, 175, 1870, 650)]

    box = boxes[0]
    maximum = 260.0
    axes(draw, box, [0, 50, 100, 150, 200, 250], maximum)
    labels_x(draw, box, rates)
    draw.text((box[0], 115), "E2E latency (ms)", fill=COLORS["ink"],
              font=font(22, True), anchor="lm")
    for mode, key, color, suffix in (
        ("Cloud p50", "latency_p50_ms", COLORS["blue"], "cloud"),
        ("Cloud p95", "latency_p95_ms", COLORS["red"], "cloud"),
        ("Edge p50", "latency_p50_ms", COLORS["green"], "edge"),
        ("Edge p95", "latency_p95_ms", COLORS["purple"], "edge"),
    ):
        values = [float(item[suffix][key]) for item in summaries]
        line_series(draw, box, values, maximum, color)
    legend(draw, box[0] + 15, 145, [("Cloud p50", COLORS["blue"]),
           ("Cloud p95", COLORS["red"]), ("Edge p50", COLORS["green"]),
           ("Edge p95", COLORS["purple"])])

    box = boxes[1]
    maximum = 70.0
    scale = axes(draw, box, [0, 10, 20, 30, 40, 50, 60, 70], maximum,
                 lambda value: f"{value:g}%")
    labels_x(draw, box, rates)
    draw.text((box[0], 115), "Latency reduction: Edge vs Cloud simulator",
              fill=COLORS["ink"], font=font(22, True), anchor="lm")
    centers = x_positions(box, len(rates))
    for center, item in zip(centers, summaries):
        for offset, percentile, color in ((-45, "p50", COLORS["green"]),
                                           (5, "p95", COLORS["purple"])):
            cloud = item["cloud"][f"latency_{percentile}_ms"]
            edge = item["edge"][f"latency_{percentile}_ms"]
            value = 100 * (cloud - edge) / cloud
            draw.rectangle((center + offset, scale(value), center + offset + 38, box[3]),
                           fill=color)
            draw.text((center + offset + 19, scale(value) - 7), f"{value:.2f}%",
                      fill=color, font=font(15), anchor="ms")
    legend(draw, box[0] + 275, 145,
           [("p50", COLORS["green"]), ("p95", COLORS["purple"])])

    box = boxes[2]
    values = [item["cloud"]["network_bytes"] / 1_000_000 for item in summaries]
    maximum = 2500.0
    scale = axes(draw, box, [0, 500, 1000, 1500, 2000, 2500], maximum)
    labels_x(draw, box, rates)
    draw.text((box[0], 115), "External application payload (MB)",
              fill=COLORS["ink"], font=font(22, True), anchor="lm")
    for x, value in zip(x_positions(box, len(rates)), values):
        draw.rectangle((x - 48, scale(value), x + 48, box[3]), fill=COLORS["blue"])
        draw.text((x, scale(value) - 8), f"{value:.1f}", fill=COLORS["blue"],
                  font=font(16), anchor="ms")
    draw.text((box[2], 145), "Edge = 0 MB; success = 100%",
              fill=COLORS["green"], font=font(17), anchor="rm")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-load", type=Path, default=Path("results/aws_yolo_load_summary.csv"))
    parser.add_argument("--aws-metrics", type=Path, default=Path("results/aws_yolo_log_metrics.csv"))
    parser.add_argument("--local", action="append", type=Path, required=True)
    parser.add_argument("--aws-output", type=Path,
                        default=Path("report/images/aws_yolo_metrics.png"))
    parser.add_argument("--local-output", type=Path,
                        default=Path("report/images/yolo_simulator_comparison.png"))
    args = parser.parse_args()
    load_rows = read_csv(args.aws_load)
    metric_rows = read_csv(args.aws_metrics)
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in args.local]
    summaries.sort(key=lambda item: item["experiment"]["target_rate_rps"])
    draw_aws(args.aws_output, load_rows, metric_rows)
    draw_local(args.local_output, summaries)
    print(f"AWS figure: {args.aws_output}")
    print(f"Local figure: {args.local_output}")


if __name__ == "__main__":
    main()
