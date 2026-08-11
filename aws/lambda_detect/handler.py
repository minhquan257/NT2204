import time
from pathlib import Path

import boto3

# Đóng gói edge_demo/ cùng Lambda hoặc thay bằng code YOLOv8 thực tế.
from edge_demo.core import DeterministicDetector


detector = DeterministicDetector()


def handler(event, context):
    started = time.perf_counter()
    # Step Functions chỉ chuyển bucket/key; ảnh lớn không đi qua workflow state.
    if "bucket" in event:
        image_path = Path("/tmp") / Path(event["key"]).name
        boto3.client("s3").download_file(event["bucket"], event["key"], str(image_path))
    else:  # hỗ trợ smoke test cục bộ
        image_path = Path(event["local_path"])
    result = detector.detect(event["request_id"], image_path)
    return {
        "request_id": result.request_id,
        "image_name": result.image_name,
        "detections": [
            {"label": d.label, "confidence": d.confidence, "box": list(d.box)}
            for d in result.detections
        ],
        "stage_latency_ms": (time.perf_counter() - started) * 1000
    }
