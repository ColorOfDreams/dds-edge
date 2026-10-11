# DDS-Edge: Deep Learning, câu hỏi nghiên cứu và thang đo (chốt 11/10/2026)

## Câu hỏi nghiên cứu
Khi bị giới hạn tài nguyên như thiết bị edge, ta đánh đổi bao nhiêu độ chính xác trên tài xế chưa từng thấy, và có cách nào thu hẹp khoảng cách đó không? Đồng thời model nào thực sự khả thi để đưa vào edge AI?

Đây là nghiên cứu ứng dụng: không chỉ so điểm, mà đo cả tốc độ và tính khả thi triển khai. Không loại trừ model nào chỉ vì nhẹ hay nặng; model lớn vẫn được đưa vào làm mốc.

## Giao thức cố định (để so sánh công bằng)
- Dữ liệu: State Farm Distracted Driver, 6 lớp (grouped6). Roboflow và dữ liệu tự quay để sau.
- Chia tập theo tài xế (group), seed 42, ghi trong manifest.csv (khoảng 18/4/4 tài xế).
- Chọn epoch và cấu hình theo val macro-F1. Test báo cáo một lần cho cấu hình đã chọn.
- Pretrained ImageNet, fine-tune toàn bộ, không lật ngang ảnh.

## Thang đo cho mỗi model
| Nhóm | Chỉ số |
|---|---|
| Chất lượng | macro-F1 và F1 từng lớp (float), macro-F1 sau INT8, mức tụt do INT8 |
| Kích thước | Số tham số, MB bản float, MB bản INT8 |
| Tính toán | MACs/FLOPs |
| Tốc độ | Độ trễ một ảnh trên CPU (ONNX Runtime, batch 1, 1 luồng), median và p95. Chỉ để xếp hạng tương đối giữa các model, chưa phải số đo trên thiết bị |
| Khả thi edge | Xuất ONNX được không (không toán tử lạ); lượng tử hóa INT8 chạy được và tụt bao nhiêu; toán tử có nằm trong danh sách hỗ trợ của chip mục tiêu (kiểm khi chốt thiết bị) |

## Cách đọc kết quả
1. Cổng khả thi: loại model không xuất được ONNX, không lượng tử hóa được, hoặc tụt F1 INT8 quá mức chấp nhận (giả định ban đầu: khoảng 2 điểm macro-F1, cần xác nhận lại).
2. Trong số model qua cổng, vẽ biểu đồ macro-F1 theo độ trễ hoặc kích thước.
3. Ngưỡng độ trễ tuyệt đối chỉ áp dụng khi đo trên thiết bị thật; số đo CPU máy tính dùng để so sánh tương đối.

## Ứng viên model (mở rộng dần, chưa loại ai)
MobileNetV3-Small (mục tiêu), EfficientNet-Lite0, ResNet18, và các model lớn hơn làm mốc (ví dụ ResNet50). Có thể thêm MobileNetV3-Large, ShuffleNetV2. `build_model` hiện chỉ hỗ trợ ba kiến trúc đầu.

## Thí nghiệm theo thứ tự ưu tiên
1. Baseline MobileNetV3-Small pretrained + mốc "đoán lớp đa số".
2. Export ONNX + INT8 PTQ + độ trễ CPU cho baseline (export_quantize).
3. Thêm 1-2 model (ResNet18, EfficientNet-Lite0 hoặc ResNet50 làm mốc), cùng giao thức.
4. Thu hẹp khoảng cách cho model nhỏ: giữ tỉ lệ ảnh/độ phân giải, augmentation, distillation nếu còn thời gian.
5. Nếu còn: pretrained so với train từ đầu.

## Chưa làm trong bài này
Roboflow, dữ liệu tự quay, fine-tune sang nguồn khác, đo trên thiết bị edge thật, nhiều seed. Các phần này thuộc đồ án 3.

## Lưu ý
- Điểm của bài không so được với bảng xếp hạng Kaggle (khác chỉ số và cách chia).
- Giấy phép: ImageNet pretrained và thư viện như Ultralytics (AGPL) cần kiểm tra lại nếu sau này làm sản phẩm thật; với bài tập thì không ảnh hưởng.