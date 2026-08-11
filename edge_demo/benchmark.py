from __future__ import annotations

import csv
import json
import math
import resource
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .orchestration import CloudOrchestratorSimulator, EdgeOrchestrator


@dataclass(frozen=True)
class Row:
    request_id: str
    mode: str
    image: str
    success: bool
    intrusion: bool
    latency_ms: float
    service_latency_ms: float
    orchestration_ms: float
    network_bytes: int
    scheduled_at_s: float
    completed_at_s: float


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def run_load(
    orchestrator, images: list[Path], requests: int, rate: float, workers: int = 4
) -> list[Row]:
    epoch = time.perf_counter()
    interval = 1.0 / rate if rate > 0 else 0.0

    def invoke_one(index: int, target: float) -> Row:
        request_id = f"{index:06d}"
        image = images[index % len(images)]
        scheduled = target - epoch
        try:
            invocation = orchestrator.invoke(request_id, image)
            completed = time.perf_counter()
            return Row(
                request_id, orchestrator.mode, image.name, True,
                invocation.result.intrusion, (completed - target) * 1000,
                invocation.latency_ms,
                invocation.orchestration_ms, invocation.network_bytes,
                scheduled, completed - epoch,
            )
        except Exception:
            return Row(
                request_id, orchestrator.mode, image.name, False, False,
                0.0, 0.0, 0.0, 0, scheduled, time.perf_counter() - epoch,
            )

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index in range(requests):
            target = epoch + index * interval
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
            futures.append(pool.submit(invoke_one, index, target))
        rows = [future.result() for future in as_completed(futures)]
    return sorted(rows, key=lambda row: row.request_id)


def summarize(rows: Iterable[Row], wall_s: float, cpu_s: float, peak_rss_bytes: int) -> dict:
    grouped = {}
    for mode in ("edge", "cloud"):
        selected = [row for row in rows if row.mode == mode]
        latency = [row.latency_ms for row in selected if row.success]
        grouped[mode] = {
            "requests": len(selected),
            "success_rate_pct": round(100 * sum(r.success for r in selected) / max(1, len(selected)), 2),
            "latency_mean_ms": round(statistics.fmean(latency), 3) if latency else 0,
            "latency_p50_ms": round(_percentile(latency, 0.50), 3),
            "latency_p95_ms": round(_percentile(latency, 0.95), 3),
            "latency_p99_ms": round(_percentile(latency, 0.99), 3),
            "network_bytes": sum(r.network_bytes for r in selected),
            "achieved_throughput_rps": round(
                len(selected) / max((r.completed_at_s for r in selected), default=1), 3
            ),
        }
    edge = grouped["edge"]["latency_p50_ms"]
    cloud = grouped["cloud"]["latency_p50_ms"]
    grouped["comparison"] = {
        "p50_reduction_pct": round(100 * (cloud - edge) / cloud, 2) if cloud else 0,
        "network_bytes_saved": grouped["cloud"]["network_bytes"] - grouped["edge"]["network_bytes"],
        "benchmark_wall_s": round(wall_s, 3),
        "process_cpu_s": round(cpu_s, 3),
        "process_peak_rss_mb": round(peak_rss_bytes / (1024 * 1024), 3),
    }
    return grouped


def write_csv(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=asdict(rows[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def read_csv(path: Path) -> list[Row]:
    with path.open(newline="", encoding="utf-8") as handle:
        result = []
        for item in csv.DictReader(handle):
            result.append(Row(
                item["request_id"], item["mode"], item["image"],
                item["success"] == "True", item["intrusion"] == "True",
                float(item["latency_ms"]), float(item.get("service_latency_ms", item["latency_ms"])),
                float(item["orchestration_ms"]),
                int(item["network_bytes"]), float(item["scheduled_at_s"]),
                float(item["completed_at_s"]),
            ))
        return result


def resource_snapshot() -> tuple[float, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports bytes; Linux/BSD generally report KiB.
    rss_bytes = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    return usage.ru_utime + usage.ru_stime, rss_bytes


def write_outputs(out_dir: Path, rows: list[Row], summary: dict) -> None:
    write_csv(out_dir / "latest.csv", rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    modes = ("edge", "cloud")
    max_latency = max(summary[m]["latency_p95_ms"] for m in modes) or 1
    bars = []
    colors = {"edge": "#16a34a", "cloud": "#2563eb"}
    for i, mode in enumerate(modes):
        value = summary[mode]["latency_p95_ms"]
        width = value / max_latency * 520
        y = 85 + i * 70
        bars.append(
            f'<text x="20" y="{y+24}">{mode.upper()}</text>'
            f'<rect x="100" y="{y}" width="{width:.1f}" height="34" fill="{colors[mode]}"/>'
            f'<text x="{110+width:.1f}" y="{y+24}">{value:.2f} ms</text>'
        )
    html = f"""<!doctype html><meta charset=utf-8><title>Edge vs Cloud</title>
<style>body{{font:16px system-ui;max-width:850px;margin:40px auto}}code{{background:#eee;padding:2px 5px}}table{{border-collapse:collapse}}td,th{{padding:8px 14px;border:1px solid #ccc}}</style>
<h1>Kết quả demo Edge vs Cloud</h1>
<p>Latency p95 (thấp hơn là tốt hơn)</p>
<svg viewBox="0 0 760 250" width="100%">{''.join(bars)}</svg>
<table><tr><th>Mode</th><th>Success</th><th>p50 (ms)</th><th>p95 (ms)</th><th>Network bytes</th></tr>
{''.join(f'<tr><td>{m}</td><td>{summary[m]["success_rate_pct"]}%</td><td>{summary[m]["latency_p50_ms"]}</td><td>{summary[m]["latency_p95_ms"]}</td><td>{summary[m]["network_bytes"]}</td></tr>' for m in modes)}</table>
<p>Giảm p50: <strong>{summary['comparison']['p50_reduction_pct']}%</strong>. Đây là số liệu mô phỏng có kiểm soát, không thay thế benchmark AWS thật.</p>"""
    (out_dir / "report.html").write_text(html, encoding="utf-8")
