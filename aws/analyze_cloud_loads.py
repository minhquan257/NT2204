#!/usr/bin/env python3
"""Summarize multiple AWS cloud-load CSV files and draw report figures."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def parse_input(value: str) -> tuple[float, Path]:
    try:
        rate_text, path_text = value.split("=", 1)
        rate = float(rate_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Định dạng phải là RATE=CSV") from exc
    return rate, Path(path_text)


def summarize(rate: float, path: Path) -> dict[str, float | int | str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    succeeded = [row for row in rows if row.get("status") == "SUCCEEDED"]
    latency = [float(row["e2e_ms"]) for row in succeeded if row.get("e2e_ms")]
    if not rows:
        raise ValueError(f"{path} không có request")
    if not latency:
        raise ValueError(f"{path} không có latency thành công")
    return {
        "rate_rps": rate,
        "source": str(path),
        "requests": len(rows),
        "succeeded": len(succeeded),
        "success_rate_pct": 100.0 * len(succeeded) / len(rows),
        "planned_duration_s": len(rows) / rate,
        "mean_ms": statistics.fmean(latency),
        "p50_ms": percentile(latency, 0.50),
        "p95_ms": percentile(latency, 0.95),
        "p99_ms": percentile(latency, 0.99),
        "min_ms": min(latency),
        "max_ms": max(latency),
        "stdev_ms": statistics.stdev(latency) if len(latency) > 1 else 0.0,
        "tail_ratio_p95_p50": percentile(latency, 0.95) / percentile(latency, 0.50),
    }


def write_summary(path: Path, summaries: list[dict[str, float | int | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summaries[0].keys())
        writer.writeheader()
        writer.writerows(summaries)


def draw_figure(path: Path, summaries: list[dict[str, float | int | str]]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    rates = [float(item["rate_rps"]) for item in summaries]
    p50 = [float(item["p50_ms"]) for item in summaries]
    p95 = [float(item["p95_ms"]) for item in summaries]
    success = [float(item["success_rate_pct"]) for item in summaries]
    canvas = Image.new("RGB", (1600, 720), "white")
    draw = ImageDraw.Draw(canvas)

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

    title_font, label_font, small_font = font(34, True), font(24), font(20)
    draw.text((800, 28), "AWS Cloud baseline under three load levels",
              fill="#111827", font=title_font, anchor="ma")

    left = (100, 120, 780, 600)
    x0, y0, x1, y1 = left
    max_latency = math.ceil(max(p95 + p50) / 200) * 200
    for tick in range(0, max_latency + 1, 200):
        y = y1 - tick / max_latency * (y1 - y0)
        draw.line((x0, y, x1, y), fill="#d1d5db", width=1)
        draw.text((x0 - 12, y), str(tick), fill="#374151", font=small_font,
                  anchor="rm")
    draw.line((x0, y0, x0, y1), fill="#111827", width=3)
    draw.line((x0, y1, x1, y1), fill="#111827", width=3)
    x_positions = [x0 + 100 + index * 230 for index in range(len(rates))]
    for x, rate in zip(x_positions, rates):
        draw.text((x, y1 + 18), f"{rate:g} rps", fill="#111827",
                  font=label_font, anchor="ma")
    for values, color, name in ((p50, "#2563eb", "p50"),
                                (p95, "#dc2626", "p95")):
        points = [(x, y1 - value / max_latency * (y1 - y0))
                  for x, value in zip(x_positions, values)]
        draw.line(points, fill=color, width=6)
        for (x, y), value in zip(points, values):
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color)
            draw.text((x, y - 16), f"{value:.1f}", fill=color,
                      font=small_font, anchor="ms")
        legend_x = x0 + 420 + (0 if name == "p50" else 120)
        draw.line((legend_x, y0 - 30, legend_x + 34, y0 - 30), fill=color, width=6)
        draw.text((legend_x + 44, y0 - 30), name, fill="#111827",
                  font=small_font, anchor="lm")
    draw.text((x0, y0 - 30), "E2E latency (ms)", fill="#111827",
              font=label_font, anchor="lm")

    right = (930, 120, 1510, 600)
    rx0, ry0, rx1, ry1 = right
    draw.line((rx0, ry0, rx0, ry1), fill="#111827", width=3)
    draw.line((rx0, ry1, rx1, ry1), fill="#111827", width=3)
    for tick in range(0, 101, 20):
        y = ry1 - tick / 100 * (ry1 - ry0)
        draw.line((rx0, y, rx1, y), fill="#d1d5db", width=1)
        draw.text((rx0 - 12, y), str(tick), fill="#374151", font=small_font,
                  anchor="rm")
    bar_width = 100
    bar_x = [rx0 + 90 + index * 180 for index in range(len(rates))]
    for x, rate, value in zip(bar_x, rates, success):
        top = ry1 - value / 100 * (ry1 - ry0)
        draw.rectangle((x, top, x + bar_width, ry1), fill="#16a34a")
        # Put the value inside the bar so a 100% label does not overlap the title.
        draw.text((x + bar_width / 2, top + 14), f"{value:.1f}%",
                  fill="white", font=small_font, anchor="ma")
        draw.text((x + bar_width / 2, ry1 + 18), f"{rate:g} rps",
                  fill="#111827", font=label_font, anchor="ma")
    draw.text((rx0, ry0 - 30), "Success rate (%)", fill="#111827",
              font=label_font, anchor="lm")

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=parse_input, required=True,
                        help="Một mức tải và CSV, ví dụ 1=results/aws_rate01.csv")
    parser.add_argument("--output", type=Path,
                        default=Path("results/aws_load_summary.csv"))
    parser.add_argument("--figure", type=Path,
                        default=Path("report/images/aws_load_latency.png"))
    args = parser.parse_args()

    summaries = [summarize(rate, path) for rate, path in sorted(args.input)]
    write_summary(args.output, summaries)
    draw_figure(args.figure, summaries)
    for item in summaries:
        print(
            f"{item['rate_rps']:g} rps: {item['succeeded']}/{item['requests']} "
            f"({item['success_rate_pct']:.2f}%), mean={item['mean_ms']:.2f} ms, "
            f"p50={item['p50_ms']:.2f} ms, p95={item['p95_ms']:.2f} ms, "
            f"p99={item['p99_ms']:.2f} ms"
        )
    print(f"Summary: {args.output}")
    print(f"Figure: {args.figure}")


if __name__ == "__main__":
    main()
