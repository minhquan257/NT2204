# Demo thật trên AWS Console

Region mặc định: `ap-southeast-1`. Stack hiện dùng Lambda container ARM64 chạy
YOLOv8n thật, lấy image từ private ECR.

## Quyền IAM cho người deploy

Nếu gặp `cloudformation:DescribeStacks AccessDenied`, đăng nhập bằng administrator
của account và gắn policy trong `aws/iam/nt2204-deployer-policy.json` cho IAM user
`quan-nguyen-nt2204`:

1. IAM → Users → `quan-nguyen-nt2204` → Permissions.
2. IAM → Policies → Create policy → JSON.
3. Dán toàn bộ file policy, chọn Next và đặt tên `NT2204DemoDeployer`.
4. Gắn customer-managed policy này vào user, chờ vài giây rồi kiểm tra bằng `aws cloudformation
   describe-stacks ...`.

Policy đã khóa account, Region, tên stack, bucket và role theo prefix của demo.

## Deploy Cloud YOLOv8n baseline

```bash
AWS_PROFILE=nt2204-new AWS_REGION=ap-southeast-1 sh aws/deploy_yolo_cloud.sh
AWS_PROFILE=nt2204-new AWS_REGION=ap-southeast-1 \
python3 aws/run_cloud_demo.py --requests 20 --rate 2
```

Sau khi chạy, lệnh in ra URL dashboard. Trên Console kiểm tra:

1. **Step Functions → State machines → nt2204-edge-chain-cloud-baseline**: mở
   Graph view và từng execution để thấy `DetectObjects → CreateAlert`.
2. **Lambda → Functions**: `*-detect-yolo` và `*-alert`; tab Monitor cho
   Duration/Invocations/Errors.
3. **ECR → Private repositories → nt2204-edge-chain-yolov8**: image và digest.
4. **CloudWatch → Dashboards → nt2204-edge-chain-dashboard**: E2E, inference,
   download, stage latency, cold model load và số execution.
5. **CloudWatch → Log groups → /aws/states/nt2204-edge-chain**: input/output và
   timestamp của workflow.
6. **S3**: bucket output của stack chứa `inputs/`.

EMF metric thường cần khoảng 1–2 phút mới xuất hiện trên dashboard. Chi phí của
Lambda/S3/Step Functions nhỏ với vài chục request nhưng không hoàn toàn bằng 0.

## Cleanup

```bash
sh aws/cleanup_cloud.sh
```

Lệnh cleanup xóa object trước vì CloudFormation không xóa được bucket còn dữ liệu.

## Greengrass Edge

Để xuất hiện ở **AWS IoT → Greengrass devices → Core devices**, cần một VM Linux
Ubuntu/Debian có Java 11+, quyền sudo và outbound Internet. Trên VM, dùng mục
“Set up one core device” trong AWS IoT Greengrass Console để nhận đúng installer
command của tài khoản/Region. Sau khi Core status là Healthy:

1. Import hai Lambda versions thành Greengrass Lambda components.
2. Đặt cả hai `pinned=true` và deploy cùng core device.
3. Lambda Detect dùng `greengrasssdk.client("lambda").invoke(...)` như
   `aws/greengrass/lambda_detect/handler.py` để gọi Alert tại local.
4. Kiểm tra **Deployments** trên Console và log local tại
   `/greengrass/v2/logs/<component>.log`.

Phần này cần thông tin VM/architecture và sẽ tạo thêm IoT Thing, certificate, role
alias và deployment. Không đưa private key/certificate vào Git.
