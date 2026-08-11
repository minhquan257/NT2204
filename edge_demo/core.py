from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class DetectionResult:
    request_id: str
    image_name: str
    detections: tuple[Detection, ...]
    inference_ms: float


@dataclass(frozen=True)
class AlertResult:
    request_id: str
    intrusion: bool
    message: str
    detection_count: int


class Detector(Protocol):
    def detect(self, request_id: str, image_path: Path) -> DetectionResult: ...


class DeterministicDetector:
    """Fast offline stand-in; stable output for a given image."""

    def __init__(self, inference_ms: float = 8.0) -> None:
        self.inference_ms = inference_ms

    def detect(self, request_id: str, image_path: Path) -> DetectionResult:
        started = time.perf_counter()
        digest = hashlib.sha256(image_path.read_bytes()).digest()
        time.sleep(self.inference_ms / 1000)
        # Roughly 2/3 of sample inputs contain a person; deterministic by bytes.
        labels = ("person", "car", "person")
        label = labels[digest[0] % len(labels)]
        confidence = round(0.55 + (digest[1] / 255) * 0.44, 3)
        detection = Detection(label, confidence, (10, 10, 100, 160))
        elapsed = (time.perf_counter() - started) * 1000
        return DetectionResult(request_id, image_path.name, (detection,), elapsed)


class YoloDetector:
    def __init__(
        self,
        model: str = "yolov8n.pt",
        device: str = "cpu",
        imgsz: int = 640,
        confidence: float = 0.25,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Cài backend YOLO bằng: pip install ultralytics") from exc
        self._model = YOLO(model)
        self.device = device
        self.imgsz = imgsz
        self.confidence = confidence

    def detect(self, request_id: str, image_path: Path) -> DetectionResult:
        started = time.perf_counter()
        output = self._model(
            str(image_path),
            device=self.device,
            imgsz=self.imgsz,
            conf=self.confidence,
            verbose=False,
        )[0]
        names = output.names
        detections = []
        for box in output.boxes:
            xyxy = tuple(int(v) for v in box.xyxy[0].tolist())
            detections.append(
                Detection(names[int(box.cls[0])], float(box.conf[0]), xyxy)
            )
        elapsed = (time.perf_counter() - started) * 1000
        return DetectionResult(
            request_id, image_path.name, tuple(detections), elapsed
        )


def make_alert(result: DetectionResult, threshold: float = 0.60) -> AlertResult:
    intrusion = any(
        item.label == "person" and item.confidence >= threshold
        for item in result.detections
    )
    message = "INTRUSION_DETECTED" if intrusion else "SAFE"
    return AlertResult(result.request_id, intrusion, message, len(result.detections))


def detection_to_json(result: DetectionResult) -> bytes:
    return json.dumps(asdict(result), separators=(",", ":")).encode()


def image_envelope(request_id: str, image_path: Path) -> bytes:
    payload = {
        "request_id": request_id,
        "image_name": image_path.name,
        "image_b64": base64.b64encode(image_path.read_bytes()).decode(),
    }
    return json.dumps(payload, separators=(",", ":")).encode()
