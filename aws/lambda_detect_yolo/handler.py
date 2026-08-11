"""AWS Lambda container handler running real YOLOv8n inference."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import boto3
from ultralytics import YOLO


S3 = boto3.client("s3")
METRIC_NAMESPACE = os.getenv("METRIC_NAMESPACE", "NT2204/EdgeChain")
MODEL_PATH = os.getenv("MODEL_PATH", "/var/task/yolov8n.pt")
MODEL_IMAGE_SIZE = int(os.getenv("MODEL_IMAGE_SIZE", "640"))
MODEL_CONFIDENCE = float(os.getenv("MODEL_CONFIDENCE", "0.25"))
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "cpu")

MODEL_LOAD_STARTED = time.perf_counter()
MODEL = YOLO(MODEL_PATH)
MODEL_LOAD_MS = (time.perf_counter() - MODEL_LOAD_STARTED) * 1000
IS_COLD_START = True


def emit_metrics(request_id: str, values: dict[str, float]) -> None:
    definitions = [{"Name": name, "Unit": "Milliseconds"} for name in values]
    document = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": METRIC_NAMESPACE,
                "Dimensions": [["Mode"], ["Mode", "Detector"]],
                "Metrics": definitions,
            }],
        },
        "Mode": "Cloud",
        "Detector": "YOLOv8n",
        "RequestId": request_id,
        **values,
    }
    print(json.dumps(document, separators=(",", ":")))


def handler(event, context):
    global IS_COLD_START

    started = time.perf_counter()
    request_id = event["request_id"]
    image_path = Path("/tmp") / f"{request_id}-{Path(event['key']).name}"

    download_started = time.perf_counter()
    S3.download_file(event["bucket"], event["key"], str(image_path))
    download_ms = (time.perf_counter() - download_started) * 1000

    inference_started = time.perf_counter()
    output = MODEL.predict(
        source=str(image_path),
        imgsz=MODEL_IMAGE_SIZE,
        conf=MODEL_CONFIDENCE,
        device=MODEL_DEVICE,
        verbose=False,
    )[0]
    inference_ms = (time.perf_counter() - inference_started) * 1000

    detections = []
    for box in output.boxes:
        detections.append({
            "label": output.names[int(box.cls[0])],
            "confidence": round(float(box.conf[0]), 6),
            "box": [round(float(value), 2) for value in box.xyxy[0].tolist()],
        })

    try:
        image_path.unlink()
    except FileNotFoundError:
        pass

    detect_ms = (time.perf_counter() - started) * 1000
    metrics = {
        "DetectLatency": detect_ms,
        "ImageDownloadLatency": download_ms,
        "ModelInferenceLatency": inference_ms,
    }
    if IS_COLD_START:
        metrics["ModelLoadLatency"] = MODEL_LOAD_MS
        IS_COLD_START = False
    emit_metrics(request_id, metrics)

    return {
        "request_id": request_id,
        "started_at_ms": event["started_at_ms"],
        "image_name": Path(event["key"]).name,
        "detector": "YOLOv8n",
        "model_imgsz": MODEL_IMAGE_SIZE,
        "model_confidence": MODEL_CONFIDENCE,
        "detections": detections,
        "detect_latency_ms": detect_ms,
        "inference_latency_ms": inference_ms,
    }
