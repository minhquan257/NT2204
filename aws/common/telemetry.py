import json
import os
import time


def emit(metric_name, value, mode, request_id):
    """CloudWatch Embedded Metric Format; printed JSON becomes a metric."""
    now_ms = int(time.time() * 1000)
    print(json.dumps({
        "_aws": {
            "Timestamp": now_ms,
            "CloudWatchMetrics": [{
                "Namespace": os.getenv("METRIC_NAMESPACE", "EdgeChainDemo"),
                "Dimensions": [["Mode"]],
                "Metrics": [{"Name": metric_name, "Unit": "Milliseconds"}]
            }]
        },
        "Mode": mode,
        "RequestId": request_id,
        metric_name: value
    }))
