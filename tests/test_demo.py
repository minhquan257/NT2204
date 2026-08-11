import tempfile
import unittest
from pathlib import Path

from edge_demo.benchmark import run_load, summarize
from edge_demo.core import DeterministicDetector
from edge_demo.orchestration import CloudOrchestratorSimulator, EdgeOrchestrator


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.image = Path(self.temp.name) / "frame.jpg"
        self.image.write_bytes(b"synthetic-image")

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_request_id_and_no_edge_network_io(self):
        invocation = EdgeOrchestrator(DeterministicDetector(0)).invoke("abc", self.image)
        self.assertEqual(invocation.result.request_id, "abc")
        self.assertEqual(invocation.network_bytes, 0)

    def test_cloud_has_handoff_cost(self):
        edge = EdgeOrchestrator(DeterministicDetector(0)).invoke("x", self.image)
        cloud = CloudOrchestratorSimulator(DeterministicDetector(0), 2, 2, 2).invoke("x", self.image)
        self.assertGreater(cloud.network_bytes, edge.network_bytes)
        self.assertGreater(cloud.latency_ms, edge.latency_ms)

    def test_load_handles_every_request(self):
        rows = run_load(EdgeOrchestrator(DeterministicDetector(0)), [self.image], 5, 1000)
        summary = summarize(rows, 0, 0, 0)
        self.assertEqual(len(rows), 5)
        self.assertEqual(summary["edge"]["success_rate_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()

