# Demo: tối ưu độ trễ chuỗi hàm AI thị giác tại Edge

Demo so sánh cùng một chuỗi `Detect -> Alert` theo hai đường điều phối:

```text
Cloud: Image -> upload/JSON -> Step Functions -> Detect -> state handoff -> Alert
Edge : Image -> LocalOrchestrator -> Detect -------- direct call --------> Alert
```

Chế độ mặc định là mô phỏng có kiểm soát, chạy hoàn toàn offline và không cần tài
khoản AWS. Mục tiêu là trình diễn/đo **chi phí điều phối**, không tuyên bố độ chính
xác của YOLO. Thư mục `aws/` chứa các artifact tham khảo để triển khai thật.

## Chạy nhanh

Yêu cầu Python 3.10+ và không cần cài package ngoài:

```bash
python3 -m edge_demo.cli benchmark --images sample_images --requests 60 --rate 10
python3 -m edge_demo.cli summarize results/latest.csv
```

Kết quả gồm:

- `results/latest.csv`: từng request, latency, trạng thái, byte mạng ước tính;
- `results/summary.json`: p50/p95/p99, throughput, success rate, CPU/RAM;
- `results/report.html`: biểu đồ mở trực tiếp bằng trình duyệt.

Chạy kiểm thử:

```bash
python3 -m unittest discover -s tests -v
```

## Demo khi thuyết trình (3–5 phút)

1. Mở sơ đồ trong `report/BAO_CAO_DEMO.md`, giải thích BA6/BA7 và IC4 của bài báo.
2. Chạy benchmark ở 5 request/s, sau đó 10 và 20 request/s.
3. Mở `results/report.html`, so sánh p50/p95 và Network I/O.
4. Mở một dòng CSV để chứng minh `request_id` xuất hiện đúng một lần ở mỗi mode.
5. Nêu rõ số liệu mô phỏng chỉ kiểm chứng giả thuyết; số liệu kết luận phải lấy từ
   phần cứng/mạng AWS thật và lặp ít nhất 30 lần cho mỗi cấu hình.

## Dùng YOLOv8 thật

Demo mặc định dùng detector tất định. Để chạy suy luận YOLOv8n thật trong môi
trường riêng (phù hợp cả khi Python mặc định của máy quá mới cho PyTorch):

```bash
/usr/bin/python3 -m venv .venv-yolo
.venv-yolo/bin/python -m pip install --upgrade pip setuptools wheel
.venv-yolo/bin/python -m pip install ultralytics

YOLO_CONFIG_DIR=results/.ultralytics \
MPLCONFIGDIR=results/.matplotlib \
.venv-yolo/bin/python -m edge_demo.cli benchmark \
  --images sample_images --requests 30 --rate 2 --workers 4 \
  --detector yolo --model yolov8n.pt --device cpu --imgsz 640 \
  --confidence 0.25 --warmup 3 --output results/yolo_pilot
```

`--warmup 3` loại ba lần suy luận khởi động của mỗi mode khỏi tập đo. Chương trình
chỉ đọc các định dạng ảnh hỗ trợ và bỏ qua PDF, `.DS_Store`. Cấu hình mô hình,
device, kích thước đầu vào và tải được ghi trong `summary.json`.

Chạy đầy đủ ba mức tải 1, 3 và 5 request/s (180 giây cho mỗi mode ở mỗi mức):

```bash
sh scripts/run_yolo_experiments.sh
```

Toàn bộ ma trận mất khoảng 18 phút vì Edge và Cloud simulator được đo lần lượt.
Kết quả nằm trong `results/yolo_rate01`, `results/yolo_rate03` và
`results/yolo_rate05`. Lần đầu Ultralytics có thể tải trọng số từ mạng; hãy tải
sẵn trước buổi demo.

Đường AWS hiện tại cũng đã dùng YOLOv8n thật. Build và triển khai Lambda container:

```bash
AWS_PROFILE=nt2204-new AWS_REGION=ap-southeast-1 sh aws/deploy_yolo_cloud.sh
```

Số liệu AWS YOLOv8n nằm trong `results/aws_yolo_rate01.csv`,
`results/aws_yolo_rate03.csv`, `results/aws_yolo_rate05.csv` và được tách khỏi kết
quả simulator. Xem bảng/hình đã tổng hợp tại
`report/YOLOV8_RESULTS_AND_SLIDES.md`.

## Giới hạn cần ghi trong báo cáo

- `success_rate=100%` nghĩa là xử lý đủ request, **không phải** YOLO chính xác 100%.
- Cloud mode cục bộ mô phỏng network/Step Functions bằng độ trễ cấu hình được.
- Greengrass IPC là local inter-process communication; không đồng nghĩa chia sẻ
  cùng vùng nhớ giữa hai Lambda.
- Network byte trong mô phỏng là byte payload ở tầng ứng dụng, không gồm TLS/IP.
# NT2204
