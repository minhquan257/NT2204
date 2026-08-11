from __future__ import annotations

import time
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from .core import AlertResult, Detector, detection_to_json, image_envelope, make_alert


@dataclass(frozen=True)
class Invocation:
    result: AlertResult
    latency_ms: float
    network_bytes: int
    orchestration_ms: float


class EdgeOrchestrator:
    """Co-located synchronous dataflow; no remote intermediate state."""

    mode = "edge"

    def __init__(self, detector: Detector) -> None:
        self.detector = detector

    def invoke(self, request_id: str, image_path: Path) -> Invocation:
        started = time.perf_counter()
        detection = self.detector.detect(request_id, image_path)
        before_handoff = time.perf_counter()
        result = make_alert(detection)
        ended = time.perf_counter()
        return Invocation(
            result=result,
            latency_ms=(ended - started) * 1000,
            network_bytes=0,
            orchestration_ms=(ended - before_handoff) * 1000,
        )


class CloudOrchestratorSimulator:
    """Controlled approximation of upload + Step Functions state transitions."""

    mode = "cloud"

    def __init__(
        self,
        detector: Detector,
        uplink_ms: float = 35.0,
        transition_ms: float = 20.0,
        downlink_ms: float = 35.0,
    ) -> None:
        self.detector = detector
        self.uplink_ms = uplink_ms
        self.transition_ms = transition_ms
        self.downlink_ms = downlink_ms

    def invoke(self, request_id: str, image_path: Path) -> Invocation:
        started = time.perf_counter()
        uploaded = image_envelope(request_id, image_path)
        time.sleep(self.uplink_ms / 1000)

        detection = self.detector.detect(request_id, image_path)
        intermediate = detection_to_json(detection)
        orchestration_started = time.perf_counter()
        time.sleep(self.transition_ms / 1000)
        result = make_alert(detection)
        returned = json.dumps(asdict(result), separators=(",", ":")).encode()
        time.sleep(self.downlink_ms / 1000)
        ended = time.perf_counter()
        return Invocation(
            result=result,
            latency_ms=(ended - started) * 1000,
            # External edge-cloud payload only. `intermediate` is an internal
            # Step Functions handoff and is deliberately not counted as uplink.
            network_bytes=len(uploaded) + len(returned),
            orchestration_ms=(ended - orchestration_started) * 1000,
        )
