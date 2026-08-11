# Greengrass v2 deployment notes

Hai handler minh họa cơ chế Lambda 1 gọi Lambda 2 bằng Greengrass Lambda SDK ở
local IPC. Khi đóng gói thành component, cần:

1. Cài AWS IoT Greengrass Core v2 và component `aws.greengrass.LambdaLauncher`.
2. Đóng gói mỗi handler cùng dependency/model thành ZIP và tạo Lambda component.
3. Đặt `pinned=true` để giảm cold start trong benchmark.
4. Cho Lambda Detect quyền `aws.greengrass.ipc.lambda:invoke` đối với resource của
   Lambda Alert trong accessControl của recipe.
5. Giữ cùng model, ảnh, memory limit và warm-up giữa hai kịch bản.

Tên function/resource phụ thuộc recipe và phiên bản component thực tế, vì vậy file
handler dùng biến `ALERT_FUNCTION` thay vì hard-code ARN. Log `request_id`, thời
điểm nhận ảnh, sau inference, sau IPC và hoàn tất để truy vết không mất/trùng request.

Lưu ý: `greengrasssdk` dành cho Lambda component tương thích Greengrass. Nếu dùng
generic component, hãy dùng Greengrass Core IPC SDK `awsiot.greengrasscoreipc` và
operation `InvokeLocalLambda` tương ứng.
