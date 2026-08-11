# Bộ số liệu và nội dung slide — YOLOv8n thật

## 1. Cấu hình phải ghi thống nhất

- Model: `yolov8n.pt` (6,55 MB), pretrained COCO.
- Runtime: Ultralytics 8.4.117, PyTorch 2.8.0 CPU-only.
- Input size: 640 px; detection confidence: 0,25.
- Alert: `person` có confidence >= 0,60.
- AWS Detect: Lambda container Linux ARM64, 3008 MB RAM, 1024 MB `/tmp`, timeout 120 giây.
- AWS flow: S3 -> Step Functions -> Lambda Detect YOLOv8n -> Lambda Alert -> CloudWatch.
- Local controlled experiment: cùng trọng số và tham số; warm-up 3 request cho mỗi mode.
- Tập đầu vào: 3 ảnh, không phải dataset có nhãn; không báo cáo precision/recall/mAP.

## 2. AWS Lambda YOLOv8n — kết quả chính

| Chỉ số | 1 rps | 3 rps | 5 rps |
|---|---:|---:|---:|
| Request | 180 | 540 | 900 |
| Thành công | 180 | 540 | 900 |
| Success rate | 100% | 100% | 100% |
| Mean E2E (ms) | 968,15 | 856,67 | 925,56 |
| p50 E2E (ms) | 966,56 | 842,85 | 921,08 |
| p95 E2E (ms) | 1.076,56 | 978,10 | 1.080,49 |
| p99 E2E (ms) | 1.155,17 | 1.081,76 | 1.182,76 |
| Maximum (ms) | 1.293,42 | 1.708,99 | 2.451,32 |
| Throughput thực (rps) | 0,999 | 2,983 | 4,956 |

## 3. Phân rã AWS theo đúng request ID

| Metric trung bình | 1 rps | 3 rps | 5 rps |
|---|---:|---:|---:|
| Detect stage (ms) | 357,104 | 244,440 | 289,559 |
| YOLO inference (ms) | 306,660 | 194,452 | 240,028 |
| S3 download (ms) | 49,765 | 49,357 | 48,874 |
| Alert predicate (µs) | 5,307 | 5,396 | 5,533 |
| Lambda Detect Duration (ms) | 359,021 | 246,246 | 291,450 |
| Lambda Alert Duration (ms) | 2,067 | 1,705 | 1,781 |
| Phần dư ngoài hai Lambda (ms) | 607,066 | 608,719 | 632,324 |

Phần dư là `Mean E2E - Detect Duration - Alert Duration`. Không gọi phần dư này là
“Step Functions latency thuần túy” vì nó còn gồm StartExecution, lập lịch,
Lambda invocation và chuyển trạng thái.

### Cold và warm invocation

- Cold đầu tiên sau deploy: E2E 64.408,20 ms; Detect 16.136,78 ms; inference
  15.754,27 ms; Lambda REPORT Duration 52.936,51 ms; `INIT_REPORT` chạm 9.999,96 ms.
- Warm kế tiếp: E2E 1.974,89 ms; Detect 363,59 ms; inference 271,32 ms.
- Năm invocation đồng thời được dùng làm warm-up và không tính vào 1.620 request chính.

## 4. YOLOv8n thật trong Edge/Cloud simulator

| Chỉ số | Cloud 1 | Edge 1 | Cloud 3 | Edge 3 | Cloud 5 | Edge 5 |
|---|---:|---:|---:|---:|---:|---:|
| Request | 180 | 180 | 540 | 540 | 900 | 900 |
| Success rate | 100% | 100% | 100% | 100% | 100% | 100% |
| Mean (ms) | 185,645 | 71,170 | 189,955 | 71,625 | 172,497 | 68,637 |
| p50 (ms) | 185,953 | 75,003 | 190,400 | 75,001 | 170,510 | 67,515 |
| p95 (ms) | 226,466 | 96,882 | 228,535 | 98,087 | 213,872 | 94,718 |
| p99 (ms) | 241,432 | 103,145 | 240,155 | 102,303 | 243,307 | 98,256 |
| Throughput (rps) | 1,005 | 1,005 | 3,002 | 3,004 | 5,001 | 5,004 |
| External payload (MB) | 448,073 | 0 | 1.344,219 | 0 | 2.240,365 | 0 |

- Giảm p50: 59,67%; 60,61%; 60,40%.
- Giảm p95: 57,22%; 57,08%; 55,71%.
- Payload Cloud: 2,489294 MB/request; Edge simulator: 0 external byte.
- Đây là simulator trong cùng tiến trình, không phải số đo Greengrass IPC.

## 5. Hình dùng trong báo cáo và slide

1. `report/images/aws_yolo_load_latency.png` — p50, p95 và success rate AWS.
2. `report/images/aws_yolo_metrics.png` — E2E, Detect breakdown, Lambda Duration,
   Step Functions execution.
3. `report/images/yolo_simulator_comparison.png` — Cloud/Edge simulator, phần trăm
   giảm latency và payload.
4. `report/images/yolov8_detection_examples.png` — bounding box thật trên ba ảnh.

Không dùng lại `aws_load_latency.png` hoặc `aws_cloudwatch_metrics.png` vì đó là
số liệu detector tất định cũ.

Nguồn số liệu chuẩn để trích dẫn:

- `results/aws_yolo_load_summary.csv`: percentile E2E của đúng 1.620 request.
- `results/aws_yolo_log_metrics.csv`: stage và Lambda Duration ghép chính xác theo
  request ID, không gồm warm-up.
- `results/yolo_rate01|03|05/summary.json`: kết quả simulator YOLOv8n thật.

Không dùng `results/aws_yolo_cloudwatch_summary.csv` cho mức 1 rps vì cửa sổ
CloudWatch 60 giây của file này chứa thêm 5 warm-up. File được giữ lại như dữ liệu
trung gian; báo cáo đã dùng `aws_yolo_log_metrics.csv` để loại nhiễu.

## 6. Nội dung thay thế theo slide

### Slide 1 — Tiêu đề

**Đánh giá tác động của điều phối cục bộ lên độ trễ chuỗi hàm AI thị giác**

Phụ đề: *Thực nghiệm YOLOv8n thật trên AWS Lambda container và Edge/Cloud simulator*.

### Slide 2 — Nội dung trình bày

1. Bối cảnh và định hướng từ bài báo.
2. Kiến trúc AWS YOLOv8n và Edge simulator.
3. Thiết kế thực nghiệm 1/3/5 rps.
4. Kết quả AWS, phân rã latency và cold start.
5. So sánh điều phối cục bộ, giới hạn và kết luận.

### Slide 3 — Bối cảnh và câu hỏi nghiên cứu

- Chuỗi xử lý: ảnh -> YOLOv8n Detect -> Alert -> cảnh báo.
- E2E không chỉ gồm inference mà còn S3, điều phối, invocation và handoff.
- Câu hỏi: khi giữ nguyên model và logic Alert, gọi cục bộ thay đổi p50/p95 và
  external payload như thế nào so với đường Cloud mô phỏng?

### Slide 4 — Định hướng từ bài báo

- BA6: remote state tạo chi phí latency/băng thông.
- BA7: function handoff không thể mặc định là miễn phí.
- BA9: điều phối tập trung phụ thuộc uplink.
- IC4: state placement phải là quyết định điều phối.
- Ánh xạ đo: E2E, stage latency, payload, success rate.

### Slide 5 — Phạm vi bằng chứng

**Đã đo:** Lambda YOLOv8n thật trên AWS; YOLOv8n thật ở hai nhánh simulator;
1.620 execution AWS; 3.240 invocation simulator.

**Chưa đo:** Greengrass IPC thật, mất uplink, CPU/RAM/năng lượng thiết bị,
precision/recall/mAP.

### Slide 6 — Kiến trúc hệ thống

AWS: `Image -> S3 -> Step Functions -> Lambda Detect YOLOv8n -> Lambda Alert -> CloudWatch`.

Edge simulator: `Image folder -> YOLOv8n Detect -> direct in-process call -> Alert -> CSV`.

Greengrass mục tiêu: `Local image -> Detect component -> local IPC -> Alert component`.

Nhấn mạnh: AWS và local simulator là hai nhóm bằng chứng khác môi trường, không
lấy số tuyệt đối của chúng để tính “AWS vs Edge”.

### Slide 7 — Hiện thực YOLOv8n trên AWS

- ECR private repository và Lambda container ARM64.
- Image khoảng 505 MB; PyTorch CPU-only; model 6,55 MB.
- Lambda Detect 3008 MB, timeout 120 giây, `/tmp` 1024 MB.
- Model được load ở global scope và tái sử dụng cho warm invocation.
- Metric: download, inference, Detect, Alert, E2E và Lambda Duration.

### Slide 8 — Thiết kế thực nghiệm

- 1 rps: 180 request, 4 worker, 180 giây.
- 3 rps: 540 request, 12 worker, 180 giây.
- 5 rps: 900 request, 20 worker, 180 giây.
- YOLOv8n, 640 px, confidence 0,25; Alert person >= 0,60.
- Warm-up tách khỏi tập đo; mỗi cấu hình hiện mới lặp một lần.

### Slide 9 — Kết quả AWS

Chèn `aws_yolo_load_latency.png`.

- 1.620/1.620 thành công; success rate 100%.
- p50: 966,56 / 842,85 / 921,08 ms.
- p95: 1.076,56 / 978,10 / 1.080,49 ms.
- Throughput: 0,999 / 2,983 / 4,956 rps.
- Max tại 5 rps: 2.451,32 ms — tail latency vẫn tồn tại.

### Slide 10 — Phân rã latency và cold start

Chèn `aws_yolo_metrics.png`.

- YOLO inference: 306,66 / 194,45 / 240,03 ms.
- S3 download gần 49 ms ở cả ba tải.
- Phần dư ngoài hai Lambda: 607–632 ms.
- Cold đầu tiên 64,41 giây; warm kế tiếp 1,97 giây.
- Kết luận: tối ưu model không đồng nghĩa tối ưu E2E.

### Slide 11 — Mô hình thực sự nhận diện gì?

Chèn `yolov8_detection_examples.png`.

- Person 0,730 -> kích hoạt Alert.
- Person 0,458 -> không vượt ngưỡng Alert 0,60.
- Motorcycle 0,925 -> không phải luật xâm nhập.
- 540/1.620 request AWS tạo cảnh báo; success rate không phải accuracy.

### Slide 12 — Điều phối cục bộ trong controlled simulator

Chèn `yolo_simulator_comparison.png`.

- Cùng model, ảnh, confidence, rate và warm-up.
- Edge giảm p50 khoảng 59,67–60,61%.
- Edge giảm p95 khoảng 55,71–57,22%.
- External payload giảm từ 2,489 MB/request xuống 0 trong mô hình.
- Không suy diễn tỷ lệ này thành hiệu năng Greengrass thật.

### Slide 13 — Đối chiếu bài báo và giới hạn

- BA6/IC4: payload giảm đúng hướng dự đoán khi state được giữ cục bộ.
- BA7: p50/p95 giảm khi rút ngắn handoff trong controlled simulator.
- AWS chứng minh workflow YOLOv8n hoạt động và phần ngoài handler vẫn đáng kể.
- Chưa kiểm chứng BA9/offline resilience và Greengrass IPC.
- Tập ba ảnh không dùng để đánh giá độ chính xác mô hình.

### Slide 14 — Kết luận

- Đã triển khai YOLOv8n thật bằng Lambda container và quan sát được trên AWS Console.
- 1.620/1.620 execution thành công ở 1/3/5 rps.
- YOLO inference chỉ là một phần của E2E; phần ngoài handler khoảng 607–632 ms.
- Controlled simulator cho thấy direct local orchestration giảm p50 59,67–60,61%.
- Bước tiếp theo: hai Greengrass component, local IPC, lặp workload ít nhất 5 lần,
  đo CPU/RAM/network và thử mất uplink.

### Slide cuối — Cảm ơn

Giữ tối giản. Có thể đặt QR/link CloudWatch dashboard và repository, không thêm số
liệu mới ở slide này.
