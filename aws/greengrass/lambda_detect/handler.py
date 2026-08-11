"""Greengrass Lambda 1: inference then direct local invocation of Lambda 2."""
import json
import os
import time

import greengrasssdk


lambda_client = greengrasssdk.client("lambda")
ALERT_FUNCTION = os.getenv("ALERT_FUNCTION", "IntrusionAlert")


def handler(event, context):
    started = time.perf_counter()
    # Thay khối này bằng YOLOv8; payload chỉ chứa kết quả nhỏ, không chứa ảnh.
    detection = {
        "request_id": event["request_id"],
        "detections": [{"label": "person", "confidence": 0.91, "box": [10, 10, 100, 160]}]
    }
    response = lambda_client.invoke(
        FunctionName=ALERT_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(detection).encode("utf-8")
    )
    return {
        "request_id": event["request_id"],
        "alert": json.loads(response["Payload"].read()),
        "edge_e2e_ms": (time.perf_counter() - started) * 1000
    }
