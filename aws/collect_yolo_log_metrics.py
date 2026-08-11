#!/usr/bin/env python3
"""Extract per-request YOLO and Lambda metrics from CloudWatch Logs."""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


START_RE = re.compile(r"START RequestId: ([\w-]+)")
REPORT_RE = re.compile(r"REPORT RequestId: ([\w-]+).*?Duration: ([0-9.]+) ms")


def aws_json(profile: str, region: str, *args: str) -> dict:
    command = ["aws", "--profile", profile, *args, "--region", region, "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def read_run(rate: float, path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    completed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    wall = max(float(row["completed_at_s"]) for row in rows)
    return {
        "rate": rate,
        "path": path,
        "rows": rows,
        "ids": {row["request_id"] for row in rows},
        "start": completed - timedelta(seconds=wall),
        "end": completed,
    }


def fetch_events(profile: str, region: str, group: str,
                 start: datetime, end: datetime) -> list[dict]:
    response = aws_json(
        profile, region, "logs", "filter-log-events",
        "--log-group-name", group,
        "--start-time", str(int(start.timestamp() * 1000)),
        "--end-time", str(int(end.timestamp() * 1000)),
    )
    return response.get("events", [])


def parse_events(events: list[dict]) -> tuple[dict[str, float], dict[str, dict]]:
    by_stream: dict[str, list[dict]] = {}
    for event in events:
        by_stream.setdefault(event["logStreamName"], []).append(event)

    durations: dict[str, float] = {}
    application_metrics: dict[str, dict] = {}
    for stream_events in by_stream.values():
        current_lambda_id = None
        current_application_id = None
        for event in sorted(stream_events, key=lambda item: (item["timestamp"], item["eventId"])):
            message = event["message"]
            start_match = START_RE.search(message)
            if start_match:
                current_lambda_id = start_match.group(1)
                current_application_id = None
                continue

            json_start = message.find("{")
            if json_start >= 0:
                try:
                    document = json.loads(message[json_start:])
                except json.JSONDecodeError:
                    document = None
                if isinstance(document, dict) and document.get("RequestId"):
                    current_application_id = str(document["RequestId"])
                    application_metrics[current_application_id] = document

            report_match = REPORT_RE.search(message)
            if report_match and current_application_id:
                if current_lambda_id is None or report_match.group(1) == current_lambda_id:
                    durations[current_application_id] = float(report_match.group(2))
                current_lambda_id = None
                current_application_id = None
    return durations, application_metrics


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="nt2204-new")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--stack", default="nt2204-edge-chain")
    parser.add_argument("--input", action="append", required=True,
                        help="RATE=CSV")
    parser.add_argument("--output", type=Path,
                        default=Path("results/aws_yolo_log_metrics.csv"))
    args = parser.parse_args()

    runs = []
    for item in args.input:
        rate_text, path_text = item.split("=", 1)
        runs.append(read_run(float(rate_text), Path(path_text)))
    runs.sort(key=lambda item: item["rate"])
    start = min(item["start"] for item in runs) - timedelta(seconds=30)
    end = max(item["end"] for item in runs) + timedelta(seconds=30)

    detect_events = fetch_events(
        args.profile, args.region, f"/aws/lambda/{args.stack}-detect-yolo", start, end
    )
    alert_events = fetch_events(
        args.profile, args.region, f"/aws/lambda/{args.stack}-alert", start, end
    )
    detect_duration, detect_metrics = parse_events(detect_events)
    alert_duration, alert_metrics = parse_events(alert_events)

    summaries = []
    for run in runs:
        ids = run["ids"]
        rows = run["rows"]
        detect_docs = [detect_metrics[item] for item in ids if item in detect_metrics]
        alert_docs = [alert_metrics[item] for item in ids if item in alert_metrics]
        detect_durations = [detect_duration[item] for item in ids if item in detect_duration]
        alert_durations = [alert_duration[item] for item in ids if item in alert_duration]
        summary = {
            "rate_rps": run["rate"],
            "requests": len(rows),
            "successes": sum(row["status"] == "SUCCEEDED" for row in rows),
            "detector_yolov8n_rows": sum(row.get("detector") == "YOLOv8n" for row in rows),
            "detect_stage_avg_ms": mean([float(row["detect_ms"]) for row in rows]),
            "model_inference_avg_ms": mean([float(row["inference_ms"]) for row in rows]),
            "image_download_avg_ms": mean([float(doc["ImageDownloadLatency"]) for doc in detect_docs]),
            "alert_stage_avg_ms": mean([float(doc["AlertLatency"]) for doc in alert_docs]),
            "lambda_detect_duration_avg_ms": mean(detect_durations),
            "lambda_alert_duration_avg_ms": mean(alert_durations),
            "detect_log_samples": len(detect_docs),
            "alert_log_samples": len(alert_docs),
            "lambda_detect_samples": len(detect_durations),
            "lambda_alert_samples": len(alert_durations),
            "model_load_max_ms": max(
                (float(doc["ModelLoadLatency"]) for doc in detect_docs if "ModelLoadLatency" in doc),
                default=0.0,
            ),
        }
        summaries.append(summary)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summaries[0].keys())
        writer.writeheader()
        writer.writerows(summaries)
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    print(f"CSV: {args.output}")


if __name__ == "__main__":
    main()
