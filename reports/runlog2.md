# Runlog 2: baseline MobileNetV3-Small, 10 epoch (`runs/mnv3_pre_aug`)

**Lệnh:** `python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --name mnv3_pre_aug`

## Mới so với runlog 1
- `epochs`: 1 → **10** (mặc định). Lịch cosine giờ trải đều qua 10 epoch.
- Mọi thứ khác giữ nguyên: dữ liệu, chia tập, xử lý ảnh, augmentation, mô hình, hyperparameter (xem [runlog1.md](runlog1.md)).
- Đo thêm (số đo thật, chưa phải thay đổi huấn luyện):
  - Độ phức tạp tính toán của mô hình: **55,5 triệu MACs** cho một ảnh 224×224 (hàm `count_macs`).
  - Độ mất cân bằng lớp và mốc đoán lớp đa số, từ `prepare_data`:

| | Giá trị |
|---|---|
| Lớp lớn nhất ở train | `phone` = 41,6% |
| Tỉ lệ lớp lớn nhất / nhỏ nhất ở train | 4,48 (`phone` 6.436 ảnh so với `talk_passenger` 1.436 ảnh) |
| Mốc đoán `phone` trên test | acc 0,3952, macro-F1 0,0944 |

## Quá trình train
| Epoch | Train loss | Val acc | Val macro-F1 |
|---|---|---|---|
| 1 | 0.5933 | 0.7579 | 0.6667 |
| 2 | 0.4523 | 0.8222 | 0.7428 |
| 3 | 0.4382 | 0.7640 | 0.6389 |
| 4 | 0.4330 | 0.8396 | 0.7578 |
| 5 | 0.4279 | 0.8158 | 0.7539 |
| **6** | 0.4258 | **0.8937** | **0.8464** |
| 7 | 0.4241 | 0.8787 | 0.8307 |
| 8 | 0.4233 | 0.8810 | 0.8291 |
| 9 | 0.4230 | 0.8848 | 0.8336 |
| 10 | 0.4227 | 0.8838 | 0.8323 |

Checkpoint được chọn: epoch 6 (val macro-F1 cao nhất 0.8464).

## Kết quả test (một lần, checkpoint epoch 6)
| | Runlog 1 | **Runlog 2** | Mốc đoán đa số |
|---|---|---|---|
| Test accuracy | 0.7031 | **0.8306** | 0.3952 |
| Test macro-F1 | 0.5914 | **0.7636** | 0.0944 |

F1 từng lớp (test):

| Lớp | Runlog 1 | Runlog 2 |
|---|---|---|
| phone | 0.7568 | 0.9026 |
| reach_grooming | 0.8404 | 0.8922 |
| eat_drink | 0.7341 | 0.8035 |
| device_ops | 0.7615 | 0.8021 |
| normal | 0.4017 | 0.8017 |
| **talk_passenger** | 0.0541 | **0.3793** |

## Nhận xét
- Train 10 epoch tăng test macro-F1 thêm 0,172 so với 1 epoch; `normal` và `talk_passenger` tăng nhiều nhất.
- Val dao động mạnh ở các epoch đầu (epoch 3 tụt xuống 0.6389), ổn định từ epoch 6 khi lr giảm dần.
- Val cao hơn test (macro-F1 0.846 so với 0.764): một phần do chọn epoch theo chính val, một phần do mỗi tập chỉ có 4 tài xế nên điểm dao động theo người. Số báo cáo là số test.
- `talk_passenger` vẫn yếu nhất (F1 0.379), và cũng là lớp nhỏ nhất ở train (9,3%). Chưa xem confusion matrix nên chưa kết luận mất cân bằng là nguyên nhân.
