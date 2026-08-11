# NT2204 - Edge và Cloud AI Function Chain

Hệ thống so sánh độ trễ của cùng một chuỗi xử lý ảnh `Detect -> Alert` khi chạy
tại Edge và qua Cloud orchestration:

```text
Cloud: Image -> upload/JSON -> Step Functions -> Detect -> Alert
Edge : Image -> LocalOrchestrator -> Detect -> gọi trực tiếp -> Alert
```

Chế độ mặc định là mô phỏng offline, không cần tài khoản AWS và không cần cài thư
viện ngoài. Chế độ YOLOv8 thực hiện suy luận thật; thư mục `aws/` chứa mã triển
khai baseline lên AWS Lambda, Step Functions, S3 và CloudWatch.

## Yêu cầu

- Python 3.10 trở lên;
- ảnh đầu vào trong `sample_images/`;
- tùy chọn: Ultralytics/PyTorch để chạy YOLOv8;
- tùy chọn: AWS CLI, Docker và tài khoản AWS để triển khai Cloud.

Luôn chạy lệnh tại thư mục gốc của dự án.

## 1. Chạy nhanh bản mô phỏng offline

Không cần tạo môi trường ảo hay cài dependency:

```bash
python3 -m edge_demo.cli benchmark \
  --images sample_images \
  --requests 60 \
  --rate 10 \
  --output results
```

Xem lại thống kê từ file CSV:

```bash
python3 -m edge_demo.cli summarize results/latest.csv
```

Sau khi benchmark hoàn tất, thư mục output có:

- `latest.csv`: dữ liệu của từng request;
- `summary.json`: p50/p95/p99, throughput, success rate và tài nguyên;
- `report.html`: báo cáo trực quan, có thể mở trực tiếp bằng trình duyệt.

Các tham số hữu ích:

```bash
python3 -m edge_demo.cli benchmark --help
```

## 2. Chạy kiểm thử

```bash
python3 -m unittest discover -s tests -v
```

## 3. Chạy YOLOv8 thật tại máy local

Nên dùng môi trường ảo riêng. Nếu Python mặc định quá mới và PyTorch chưa hỗ trợ,
hãy thay `python3` bằng một bản Python 3.10-3.12 có trên máy.

```bash
python3 -m venv .venv-yolo
.venv-yolo/bin/python -m pip install --upgrade pip setuptools wheel
.venv-yolo/bin/python -m pip install -r aws/lambda_detect_yolo/requirements.txt
```

Chạy thử với YOLOv8n:

```bash
YOLO_CONFIG_DIR=results/.ultralytics \
MPLCONFIGDIR=results/.matplotlib \
.venv-yolo/bin/python -m edge_demo.cli benchmark \
  --images sample_images \
  --requests 30 \
  --rate 2 \
  --workers 4 \
  --detector yolo \
  --model yolov8n.pt \
  --device cpu \
  --imgsz 640 \
  --confidence 0.25 \
  --warmup 3 \
  --output results/yolo_pilot
```

Nếu chưa có `yolov8n.pt`, Ultralytics sẽ tải model ở lần chạy đầu. Model và kết
quả benchmark được `.gitignore` loại khỏi Git vì có thể tải hoặc tạo lại.

Chạy ma trận thí nghiệm ở 1, 3 và 5 request/giây:

```bash
sh scripts/run_yolo_experiments.sh
```

Script dùng `.venv-yolo/bin/python`, `yolov8n.pt` và `sample_images` theo mặc
định. Có thể thay đổi bằng biến môi trường `PYTHON`, `MODEL` và `IMAGES`.

## 4. Triển khai và chạy trên AWS

Trước khi chạy, cần cấu hình AWS CLI profile, Docker daemon và quyền IAM. Lệnh
sau build Lambda container ARM64, push lên ECR và deploy CloudFormation:

```bash
AWS_PROFILE=nt2204-new \
AWS_REGION=ap-southeast-1 \
sh aws/deploy_yolo_cloud.sh
```

Gửi ảnh và chạy Step Functions thật:

```bash
AWS_PROFILE=nt2204-new \
python3 aws/run_cloud_demo.py \
  --region ap-southeast-1 \
  --images sample_images \
  --requests 20 \
  --rate 2
```

Xóa tài nguyên sau khi demo để tránh phát sinh chi phí:

```bash
AWS_PROFILE=nt2204-new AWS_REGION=ap-southeast-1 sh aws/cleanup_cloud.sh
```

Hướng dẫn chi tiết về AWS Console nằm trong `aws/AWS_CONSOLE_DEMO.md`; ghi chú
triển khai Greengrass nằm trong `aws/greengrass/README.md`.

## Cấu trúc chính

```text
edge_demo/     CLI, detector và bộ điều phối Edge/Cloud mô phỏng
aws/           CloudFormation, Lambda, Step Functions và script AWS
scripts/       Script chạy ma trận benchmark YOLOv8
sample_images/ Ảnh đầu vào mẫu
tests/         Unit test
report/        Nội dung và hình ảnh phục vụ báo cáo
results/       Kết quả sinh khi chạy (không đưa lên Git)
```

## Lưu ý khi đọc kết quả

- `success_rate=100%` chỉ có nghĩa là xử lý đủ request, không phải YOLO chính xác
  100%.
- Cloud mode local mô phỏng độ trễ mạng và Step Functions; không phải số đo AWS
  thực tế.
- Network I/O trong mô phỏng là payload ở tầng ứng dụng, chưa gồm TLS/IP.
- Không commit AWS credentials, `.env`, certificate, private key, model hoặc kết
  quả benchmark. Dùng biến môi trường hoặc AWS profile cho thông tin nhạy cảm.
