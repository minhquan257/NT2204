def handler(event, context):
    intrusion = any(
        item["label"] == "person" and item["confidence"] >= 0.60
        for item in event["detections"]
    )
    return {
        "request_id": event["request_id"],
        "intrusion": intrusion,
        "message": "INTRUSION_DETECTED" if intrusion else "SAFE"
    }
