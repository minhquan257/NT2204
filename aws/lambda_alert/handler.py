def handler(event, context):
    threshold = 0.60
    intrusion = any(
        item["label"] == "person" and item["confidence"] >= threshold
        for item in event["detections"]
    )
    return {
        "request_id": event["request_id"],
        "intrusion": intrusion,
        "message": "INTRUSION_DETECTED" if intrusion else "SAFE"
    }
