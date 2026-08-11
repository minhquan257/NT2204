#!/usr/bin/env python3
"""Create a report-ready montage of real YOLOv8n detections."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=Path("sample_images"))
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--output", type=Path,
                        default=Path("report/images/yolov8_detection_examples.png"))
    args = parser.parse_args()
    images = sorted(path for path in args.images.iterdir()
                    if path.is_file() and path.suffix.lower() in EXTENSIONS)
    model = YOLO(args.model)
    results = model.predict(images, imgsz=640, conf=0.25, device="cpu", verbose=False)

    panel_width, panel_height = 600, 420
    canvas = Image.new("RGB", (panel_width * len(results), 520), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((canvas.width / 2, 25), "YOLOv8n detections on the experiment image set",
              fill="#111827", font=font(30, True), anchor="ma")
    for index, (path, result) in enumerate(zip(images, results)):
        plotted = Image.fromarray(result.plot()[..., ::-1])
        plotted.thumbnail((panel_width - 30, panel_height - 40))
        left = index * panel_width + (panel_width - plotted.width) // 2
        top = 75 + (panel_height - plotted.height) // 2
        canvas.paste(plotted, (left, top))
        detections = [
            f"{result.names[int(box.cls[0])]} {float(box.conf[0]):.3f}"
            for box in result.boxes
        ]
        summary = ", ".join(detections) if detections else "No detection >= 0.25"
        draw.text((index * panel_width + panel_width / 2, 485),
                  f"{path.name}: {summary}", fill="#111827", font=font(17), anchor="ma")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)
    print(f"Figure: {args.output}")


if __name__ == "__main__":
    main()
