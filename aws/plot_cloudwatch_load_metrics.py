#!/usr/bin/env python3
"""Draw three CloudWatch metric panels for the AWS load-test report."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLORS = {"blue": "#2563eb", "orange": "#f97316", "green": "#16a34a",
          "red": "#dc2626", "grid": "#d1d5db", "ink": "#111827"}


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


def axes(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], ticks: list[float],
         scale, formatter=lambda value: f"{value:g}") -> None:
    x0, y0, x1, y1 = box
    for tick in ticks:
        y = scale(tick)
        draw.line((x0, y, x1, y), fill=COLORS["grid"], width=1)
        draw.text((x0 - 10, y), formatter(tick), fill="#374151", font=font(17), anchor="rm")
    draw.line((x0, y0, x0, y1), fill=COLORS["ink"], width=3)
    draw.line((x0, y1, x1, y1), fill=COLORS["ink"], width=3)


def grouped_bars(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rates: list[float],
                 first: list[float], second: list[float], scale, labels: tuple[str, str],
                 formats: tuple[str, str]) -> None:
    x0, _, _, y1 = box
    centers = [x0 + 105 + index * 180 for index in range(len(rates))]
    width = 52
    baseline = scale(0.0)
    for center, rate, one, two in zip(centers, rates, first, second):
        for x, value, color, fmt in (
            (center - width - 4, one, COLORS["blue"], formats[0]),
            (center + 4, two, COLORS["orange"], formats[1]),
        ):
            top = scale(value)
            draw.rectangle((x, top, x + width, baseline), fill=color)
            label_y = max(box[1] + 5, top - 8)
            draw.text((x + width / 2, label_y), format(value, fmt), fill=color,
                      font=font(15), anchor="ms")
        draw.text((center, y1 + 15), f"{rate:g} rps", fill=COLORS["ink"],
                  font=font(19), anchor="ma")
    legend_y = box[1] - 28
    for index, (label, color) in enumerate(zip(labels, (COLORS["blue"], COLORS["orange"]))):
        x = box[0] + 245 + index * 150
        draw.rectangle((x, legend_y - 7, x + 28, legend_y + 7), fill=color)
        draw.text((x + 38, legend_y), label, fill=COLORS["ink"], font=font(16), anchor="lm")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=Path("results/aws_cloudwatch_load_summary.csv"))
    parser.add_argument("--output", type=Path,
                        default=Path("report/images/aws_cloudwatch_metrics.png"))
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    rates = [float(row["rate_rps"]) for row in rows]
    stage_detect = [float(row["detect_stage_avg_ms"]) for row in rows]
    stage_alert = [float(row["alert_stage_avg_ms"]) for row in rows]
    succeeded = [float(row["executions_succeeded_cw"]) for row in rows]
    failed = [float(row["executions_failed_cw"]) for row in rows]
    duration_detect = [float(row["lambda_detect_duration_avg_ms"]) for row in rows]
    duration_alert = [float(row["lambda_alert_duration_avg_ms"]) for row in rows]

    canvas = Image.new("RGB", (1900, 820), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((950, 32), "AWS CloudWatch metrics under three load levels",
              fill=COLORS["ink"], font=font(34, True), anchor="ma")
    # Reserve separate vertical bands for the main title, panel titles/legends,
    # and plotting areas to prevent labels from appearing crowded.
    boxes = [(85, 225, 610, 700), (720, 225, 1245, 700), (1355, 225, 1880, 700)]

    # Stage latency uses a logarithmic scale because AlertLatency is measured in microseconds.
    stage_box = boxes[0]
    log_min, log_max = -3.0, 2.0
    stage_scale = lambda value: stage_box[3] - (
        (math.log10(max(value, 10 ** log_min)) - log_min) / (log_max - log_min)
    ) * (stage_box[3] - stage_box[1])
    axes(draw, stage_box, [0.001, 0.01, 0.1, 1, 10, 100], stage_scale,
         lambda value: f"{value:g}")
    draw.text((stage_box[0], 125), "Function stage latency (ms, log scale)",
              fill=COLORS["ink"], font=font(22, True), anchor="lm")
    grouped_bars(draw, stage_box, rates, stage_detect, stage_alert, stage_scale,
                 ("Detect", "Alert"), (".2f", ".4f"))

    execution_box = boxes[1]
    execution_max = 1000.0
    execution_scale = lambda value: execution_box[3] - value / execution_max * (
        execution_box[3] - execution_box[1]
    )
    axes(draw, execution_box, [0, 200, 400, 600, 800, 1000], execution_scale)
    draw.text((execution_box[0], 125), "Step Functions executions (count)",
              fill=COLORS["ink"], font=font(22, True), anchor="lm")
    grouped_bars(draw, execution_box, rates, succeeded, failed, execution_scale,
                 ("Succeeded", "Failed"), (".0f", ".0f"))

    duration_box = boxes[2]
    duration_max = 60.0
    duration_scale = lambda value: duration_box[3] - value / duration_max * (
        duration_box[3] - duration_box[1]
    )
    axes(draw, duration_box, [0, 10, 20, 30, 40, 50, 60], duration_scale)
    draw.text((duration_box[0], 125), "Lambda Duration (ms)",
              fill=COLORS["ink"], font=font(22, True), anchor="lm")
    grouped_bars(draw, duration_box, rates, duration_detect, duration_alert,
                 duration_scale, ("Detect", "Alert"), (".2f", ".2f"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)
    print(f"Figure: {args.output}")


if __name__ == "__main__":
    main()
