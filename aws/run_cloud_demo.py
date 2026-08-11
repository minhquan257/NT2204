#!/usr/bin/env python3
"""Upload images, start real Step Functions executions, and save results."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def aws(*args: str) -> str:
    proc = subprocess.run(["aws", *args], check=True, text=True, capture_output=True)
    return proc.stdout.strip()


def output(stack: str, key: str, region: str) -> str:
    return aws("cloudformation", "describe-stacks", "--stack-name", stack,
               "--region", region, "--query",
               f"Stacks[0].Outputs[?OutputKey=='{key}'].OutputValue|[0]", "--output", "text")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stack", default="nt2204-edge-chain")
    p.add_argument("--region", default="ap-southeast-1")
    p.add_argument("--images", type=Path, default=Path("sample_images"))
    p.add_argument("--requests", type=int, default=10)
    p.add_argument("--rate", type=float, default=2.0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--output", type=Path, default=Path("results/aws_cloud.csv"))
    args = p.parse_args()
    bucket = output(args.stack, "BucketName", args.region)
    state_machine = output(args.stack, "StateMachineArn", args.region)
    images = sorted(
        x for x in args.images.iterdir()
        if x.is_file() and x.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise SystemExit("Không có ảnh đầu vào")
    for image in images:
        aws("s3", "cp", str(image), f"s3://{bucket}/inputs/{image.name}", "--region", args.region, "--only-show-errors")

    epoch = time.time()
    def one(index: int, target: float):
        image = images[index % len(images)]
        request_id = str(uuid.uuid4())
        submitted_at_s = time.time() - epoch
        started_ms = time.time() * 1000
        payload = json.dumps({"request_id":request_id,"started_at_ms":started_ms,
                              "bucket":bucket,"key":f"inputs/{image.name}"})
        arn = json.loads(aws("stepfunctions", "start-execution", "--region", args.region,
            "--state-machine-arn", state_machine, "--name", f"demo-{request_id}",
            "--input", payload))["executionArn"]
        while True:
            detail = json.loads(aws("stepfunctions", "describe-execution", "--region", args.region,
                                    "--execution-arn", arn))
            if detail["status"] not in ("RUNNING",):
                break
            time.sleep(0.2)
        result = json.loads(detail.get("output", "{}")) if detail["status"] == "SUCCEEDED" else {}
        return {"request_id":request_id,"image":image.name,"status":detail["status"],
                "detector":result.get("detector"),
                "detection_count":result.get("detection_count"),
                "intrusion":result.get("intrusion"),"e2e_ms":result.get("cloud_e2e_ms"),
                "detect_ms":result.get("detect_latency_ms"),
                "inference_ms":result.get("inference_latency_ms"),
                "scheduled_at_s":target-epoch,"submitted_at_s":submitted_at_s,
                "completed_at_s":time.time()-epoch,"execution_arn":arn}

    futures=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i in range(args.requests):
            target=epoch+i/args.rate
            if target > time.time(): time.sleep(target-time.time())
            futures.append(pool.submit(one, i, target))
        rows=[f.result() for f in as_completed(futures)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    ok=sum(r["status"]=="SUCCEEDED" for r in rows)
    latency=[float(r["e2e_ms"]) for r in rows if r["e2e_ms"] is not None]
    wall_s=max((float(r["completed_at_s"]) for r in rows), default=0.0)
    print(json.dumps({"requests":len(rows),"succeeded":ok,
                      "mean_e2e_ms":sum(latency)/len(latency) if latency else None,
                      "wall_s":wall_s,
                      "achieved_throughput_rps":len(rows)/wall_s if wall_s else None,
                      "csv":str(args.output),"dashboard":output(args.stack,"DashboardConsole",args.region)}, indent=2))


if __name__ == "__main__":
    main()
