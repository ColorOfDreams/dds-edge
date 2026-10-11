# Runlog 1: chạy thử 1 epoch (`runs/smoke`)

Mục đích: kiểm tra pipeline chạy thông. **Không dùng để báo cáo.**

**Lệnh:** `python -m dds_edge.dl.train --epochs 1 --name smoke`

## Đã làm gì

**Dữ liệu**
- State Farm Distracted Driver, chỉ thư mục `train` của Kaggle (22.424 ảnh).
- Gộp nhãn `grouped6`: normal, phone, device_ops, eat_drink, reach_grooming, talk_passenger.
- Chia theo tài xế, seed 42: train 18 / val 4 / test 4 tài xế = 15.457 / 3.915 / 3.052 ảnh (`data/processed/manifest.csv`).

**Xử lý ảnh**
- Resize thẳng về 224×224, chuẩn hoá mean/std ImageNet.
- Augmentation (chỉ train): `RandomResizedCrop` scale 0.8–1.0, xoay ±8°, đổi sáng/tương phản 30%, bão hoà 20%. Không lật ngang (sẽ đổi tay trái thành tay phải).

**Mô hình:** MobileNetV3-Small pretrained ImageNet, thay lớp cuối thành 6 đầu ra, fine-tune toàn bộ. 1.524.006 tham số.

**Hyperparameter** (mặc định, trừ epochs)

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| epochs | **1** (mặc định 10) | Số lần duyệt hết tập train |
| batch_size | 64 | Số ảnh mỗi bước cập nhật |
| lr | 0.001 | Tốc độ học ban đầu |
| optimizer | AdamW, weight_decay 1e-4 | Cập nhật trọng số, có phạt trọng số lớn |
| scheduler | Cosine annealing, T_max = epochs | lr giảm dần về 0 theo đường cosine |
| loss | CrossEntropy, label_smoothing 0.1 | Làm mềm nhãn; loss in ra không so thẳng với loss thường |
| img_size | 224 | Kích thước ảnh vào mô hình |
| seed | 42 | Hạt giống ngẫu nhiên |
| AMP | bật (GPU CUDA) | Tính số thực 16 bit cho nhanh |
| chọn checkpoint | val macro-F1 cao nhất | Test đánh giá một lần trên checkpoint này |

## Kết quả
`ep 01 loss 0.5933 val_acc 0.7579 val_f1 0.6667`

| Val acc | Val macro-F1 | **Test acc** | **Test macro-F1** |
|---|---|---|---|
| 0.7579 | 0.6667 | 0.7031 | 0.5914 |

F1 từng lớp (test): reach_grooming 0.8404, device_ops 0.7615, phone 0.7568, eat_drink 0.7341, normal 0.4017, **talk_passenger 0.0541**.

## Nhận xét
- Pipeline chạy thông: tải trọng số, train, val, test, ghi kết quả đều ổn.
- Lịch cosine bị nén hết trong 1 epoch (lr về 0 ngay trong epoch đó), nên kết quả chưa ổn định.
