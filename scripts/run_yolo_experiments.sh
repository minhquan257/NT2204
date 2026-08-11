#!/bin/sh
set -eu

PYTHON="${PYTHON:-.venv-yolo/bin/python}"
MODEL="${MODEL:-yolov8n.pt}"
IMAGES="${IMAGES:-sample_images}"

export YOLO_CONFIG_DIR="${YOLO_CONFIG_DIR:-results/.ultralytics}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-results/.matplotlib}"

"$PYTHON" -m edge_demo.cli benchmark \
  --images "$IMAGES" --requests 180 --rate 1 --workers 4 \
  --detector yolo --model "$MODEL" --device cpu --imgsz 640 \
  --confidence 0.25 --warmup 3 --output results/yolo_rate01

"$PYTHON" -m edge_demo.cli benchmark \
  --images "$IMAGES" --requests 540 --rate 3 --workers 12 \
  --detector yolo --model "$MODEL" --device cpu --imgsz 640 \
  --confidence 0.25 --warmup 3 --output results/yolo_rate03

"$PYTHON" -m edge_demo.cli benchmark \
  --images "$IMAGES" --requests 900 --rate 5 --workers 20 \
  --detector yolo --model "$MODEL" --device cpu --imgsz 640 \
  --confidence 0.25 --warmup 3 --output results/yolo_rate05
