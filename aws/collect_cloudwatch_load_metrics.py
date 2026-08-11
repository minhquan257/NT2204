#!/usr/bin/env python3
"""Collect CloudWatch metrics for the three AWS load-test CSV files."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def aws_json(profile: str, region: str, *args: str) -> dict:
    command = ["aws"]
    if profile:
        command.extend(["--profile", profile])
    command.extend([*args, "--region", region, "--output", "json"])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def parse_input(value: str) -> tuple[float, Path]:
    rate_text, path_text = value.split("=", 1)
    return float(rate_text), Path(path_text)


def metric(namespace: str, name: str, dimensions: list[dict[str, str]], stat: str) -> dict:
    return {
        "MetricStat": {
            "Metric": {
                "Namespace": namespace,
                "MetricName": name,
                "Dimensions": dimensions,
            },
            "Period": 60,
            "Stat": stat,
        },
        "ReturnData": True,
    }


def queries(state_machine_arn: str, detect_function: str, alert_function: str) -> list[dict]:
    mode = [{"Name": "Mode", "Value": "Cloud"}]
    state_machine = [{"Name": "StateMachineArn", "Value": state_machine_arn}]
    detect = [{"Name": "FunctionName", "Value": detect_function}]
    alert = [{"Name": "FunctionName", "Value": alert_function}]
    specs = [
        ("detect_stage_sum", "NT2204/EdgeChain", "DetectLatency", mode, "Sum"),
        ("detect_stage_count", "NT2204/EdgeChain", "DetectLatency", mode, "SampleCount"),
        ("alert_stage_sum", "NT2204/EdgeChain", "AlertLatency", mode, "Sum"),
        ("alert_stage_count", "NT2204/EdgeChain", "AlertLatency", mode, "SampleCount"),
        ("inference_sum", "NT2204/EdgeChain", "ModelInferenceLatency", mode, "Sum"),
        ("inference_count", "NT2204/EdgeChain", "ModelInferenceLatency", mode, "SampleCount"),
        ("download_sum", "NT2204/EdgeChain", "ImageDownloadLatency", mode, "Sum"),
        ("download_count", "NT2204/EdgeChain", "ImageDownloadLatency", mode, "SampleCount"),
        ("model_load_max", "NT2204/EdgeChain", "ModelLoadLatency", mode, "Maximum"),
        ("executions_succeeded", "AWS/States", "ExecutionsSucceeded", state_machine, "Sum"),
        ("executions_failed", "AWS/States", "ExecutionsFailed", state_machine, "Sum"),
        ("detect_duration_sum", "AWS/Lambda", "Duration", detect, "Sum"),
        ("detect_duration_count", "AWS/Lambda", "Duration", detect, "SampleCount"),
        ("alert_duration_sum", "AWS/Lambda", "Duration", alert, "Sum"),
        ("alert_duration_count", "AWS/Lambda", "Duration", alert, "SampleCount"),
    ]
    result = []
    for index, (label, namespace, name, dimensions, stat) in enumerate(specs):
        item = metric(namespace, name, dimensions, stat)
        item["Id"] = f"m{index}"
        item["Label"] = label
        result.append(item)
    return result


def sum_values(results: dict, label: str) -> float:
    for result in results.get("MetricDataResults", []):
        if result.get("Label") == label:
            return sum(float(value) for value in result.get("Values", []))
    return 0.0


def max_value(results: dict, label: str) -> float:
    for result in results.get("MetricDataResults", []):
        if result.get("Label") == label:
            values = [float(value) for value in result.get("Values", [])]
            return max(values, default=0.0)
    return 0.0


def average(results: dict, prefix: str) -> float:
    count = sum_values(results, f"{prefix}_count")
    return sum_values(results, f"{prefix}_sum") / count if count else 0.0


def collect(profile: str, region: str, rate: float, path: Path,
            state_machine_arn: str, detect_function: str, alert_function: str) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        request_count = sum(1 for _ in csv.DictReader(handle))

    # The old CSV schema has no timestamps. Its mtime is immediately after the
    # last execution completed. Use a 30-second leading pad and a 90-second
    # trailing pad so the final minute-aligned CloudWatch bucket is included.
    completed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    start = completed - timedelta(seconds=request_count / rate + 30)
    end = completed + timedelta(seconds=90)
    response = aws_json(
        profile,
        region,
        "cloudwatch",
        "get-metric-data",
        "--metric-data-queries",
        json.dumps(queries(state_machine_arn, detect_function, alert_function)),
        "--start-time",
        start.isoformat(),
        "--end-time",
        end.isoformat(),
        "--scan-by",
        "TimestampAscending",
    )
    return {
        "rate_rps": rate,
        "requests_csv": request_count,
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "detect_stage_avg_ms": average(response, "detect_stage"),
        "alert_stage_avg_ms": average(response, "alert_stage"),
        "model_inference_avg_ms": average(response, "inference"),
        "image_download_avg_ms": average(response, "download"),
        "model_load_max_ms": max_value(response, "model_load_max"),
        "executions_succeeded_cw": sum_values(response, "executions_succeeded"),
        "executions_failed_cw": sum_values(response, "executions_failed"),
        "lambda_detect_duration_avg_ms": average(response, "detect_duration"),
        "lambda_alert_duration_avg_ms": average(response, "alert_duration"),
        "detect_stage_samples": sum_values(response, "detect_stage_count"),
        "alert_stage_samples": sum_values(response, "alert_stage_count"),
        "model_inference_samples": sum_values(response, "inference_count"),
        "image_download_samples": sum_values(response, "download_count"),
        "lambda_detect_samples": sum_values(response, "detect_duration_count"),
        "lambda_alert_samples": sum_values(response, "alert_duration_count"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="nt2204-new")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--stack", default="nt2204-edge-chain")
    parser.add_argument("--input", action="append", type=parse_input, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path("results/aws_cloudwatch_load_summary.csv"))
    args = parser.parse_args()

    stack = aws_json(args.profile, args.region, "cloudformation", "describe-stacks",
                     "--stack-name", args.stack)
    outputs = {item["OutputKey"]: item["OutputValue"]
               for item in stack["Stacks"][0].get("Outputs", [])}
    state_machine_arn = outputs["StateMachineArn"]
    detect_function = outputs.get("DetectFunctionName", f"{args.stack}-detect")
    alert_function = f"{args.stack}-alert"

    rows = [
        collect(args.profile, args.region, rate, path, state_machine_arn,
                detect_function, alert_function)
        for rate, path in sorted(args.input)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"CSV: {args.output}")


if __name__ == "__main__":
    main()
