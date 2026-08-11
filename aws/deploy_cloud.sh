#!/bin/sh
set -eu
echo "Cloud baseline hiện dùng Lambda container YOLOv8n."
echo "Chuyển sang aws/deploy_yolo_cloud.sh ..."
exec sh aws/deploy_yolo_cloud.sh
