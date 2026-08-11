from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .benchmark import read_csv, resource_snapshot, run_load, summarize, write_outputs
from .core import DeterministicDetector, YoloDetector
from .orchestration import CloudOrchestratorSimulator, EdgeOrchestrator


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Edge vs cloud function-chain demo")
    commands = parser.add_subparsers(dest="command", required=True)
    bench = commands.add_parser("benchmark")
    bench.add_argument("--images", type=Path, required=True)
    bench.add_argument("--requests", type=int, default=30)
    bench.add_argument("--rate", type=float, default=5.0)
    bench.add_argument("--workers", type=int, default=4)
    bench.add_argument("--detector", choices=("mock", "yolo"), default="mock")
    bench.add_argument("--model", default="yolov8n.pt")
    bench.add_argument("--device", default="cpu")
    bench.add_argument("--imgsz", type=int, default=640)
    bench.add_argument("--confidence", type=float, default=0.25)
    bench.add_argument("--warmup", type=int, default=0)
    bench.add_argument("--inference-ms", type=float, default=8.0)
    bench.add_argument("--uplink-ms", type=float, default=35.0)
    bench.add_argument("--transition-ms", type=float, default=20.0)
    bench.add_argument("--downlink-ms", type=float, default=35.0)
    bench.add_argument("--output", type=Path, default=Path("results"))
    summary_cmd = commands.add_parser("summarize")
    summary_cmd.add_argument("csv", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "summarize":
        rows = read_csv(args.csv)
        print(json.dumps(summarize(rows, 0, 0, 0), indent=2, ensure_ascii=False))
        return

    if args.requests <= 0 or args.rate <= 0 or args.workers <= 0:
        raise SystemExit("--requests, --rate và --workers phải lớn hơn 0")
    if args.imgsz <= 0 or args.warmup < 0 or not 0 <= args.confidence <= 1:
        raise SystemExit("--imgsz phải > 0, --warmup phải >= 0 và --confidence thuộc [0, 1]")
    images = sorted(
        path
        for path in args.images.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise SystemExit(f"Không tìm thấy ảnh trong {args.images}")
    detector_factory = (
        (
            lambda: YoloDetector(
                args.model, args.device, args.imgsz, args.confidence
            )
        )
        if args.detector == "yolo"
        else (lambda: DeterministicDetector(args.inference_ms))
    )
    edge = EdgeOrchestrator(detector_factory())
    cloud = CloudOrchestratorSimulator(
        detector_factory(), args.uplink_ms, args.transition_ms, args.downlink_ms
    )
    for index in range(args.warmup):
        image = images[index % len(images)]
        edge.invoke(f"warmup-edge-{index}", image)
        cloud.invoke(f"warmup-cloud-{index}", image)
    cpu_before, _ = resource_snapshot()
    started = time.perf_counter()
    edge_rows = run_load(edge, images, args.requests, args.rate, args.workers)
    cloud_rows = run_load(cloud, images, args.requests, args.rate, args.workers)
    wall = time.perf_counter() - started
    cpu_after, peak_rss = resource_snapshot()
    rows = edge_rows + cloud_rows
    summary = summarize(rows, wall, cpu_after - cpu_before, peak_rss)
    summary["experiment"] = {
        "detector": args.detector,
        "model": args.model if args.detector == "yolo" else "deterministic",
        "device": args.device if args.detector == "yolo" else "cpu",
        "imgsz": args.imgsz if args.detector == "yolo" else None,
        "confidence": args.confidence if args.detector == "yolo" else None,
        "warmup_per_mode": args.warmup,
        "input_images": len(images),
        "requests_per_mode": args.requests,
        "target_rate_rps": args.rate,
        "workers": args.workers,
    }
    write_outputs(args.output, rows, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nĐã ghi: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
