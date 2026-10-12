# Runlog 6: ResNet50, mốc nặng (`runs/resnet50_clean`)

**Lệnh:** `python -m dds_edge.dl.train --arch resnet50 --grouping grouped6 --manifest processed/sf_320x240/manifest.csv --name resnet50_clean`

## Mới so với runlog 5
- Chỉ đổi mô hình: **ResNet50** (pretrained ImageNet, fine-tune toàn bộ), làm mốc nặng. Dữ liệu và hyperparameter giữ nguyên.
- Số tham số **23.520.326**, **4,09 tỉ MACs** (gấp 74 lần MobileNetV3-Small, gấp 10,6 lần EfficientNet-Lite0).

## Kết quả
| Epoch | Train loss | Val acc | Val macro-F1 |
|---|---|---|---|
| 1 | 0.5749 | 0.8225 | 0.7410 |
| 2 | 0.4552 | 0.8958 | 0.8369 |
| 3 | 0.4530 | 0.8969 | 0.8422 |
| 4 | 0.4464 | 0.9381 | 0.9104 |
| **5** | 0.4325 | **0.9591** | **0.9401** |
| 6 | 0.4271 | 0.9527 | 0.9273 |
| 7 | 0.4241 | 0.9049 | 0.8593 |
| 8 | 0.4223 | 0.9381 | 0.9052 |
| 9 | 0.4220 | 0.9339 | 0.8980 |
| 10 | 0.4218 | 0.9378 | 0.9050 |

Checkpoint chọn: epoch 5 (val F1 0.9401). F1 từng lớp (test): phone 0.9232, eat_drink 0.9464, device_ops 0.8141, reach_grooming 0.7609, normal 0.6457, **talk_passenger 0.3865**.

## So sánh 4 mô hình (cùng dữ liệu sạch, cùng giao thức, seed 42)
| Mô hình | Tham số | MACs | Val F1 | Test acc | **Test macro-F1** | Chênh val − test |
|---|---|---|---|---|---|---|
| MobileNetV3-Small ([3](runlog3.md)) | 1,52 M | 55,5 M | 0.8720 | 0.8380 | 0.7524 | 0.120 |
| ResNet18 ([4](runlog4.md)) | 11,18 M | 1.814 M | 0.9015 | 0.8067 | 0.7517 | 0.150 |
| **EfficientNet-Lite0** ([5](runlog5.md)) | 3,38 M | 384 M | 0.8892 | 0.8535 | **0.7860** | 0.103 |
| ResNet50 (6) | 23,52 M | 4.087 M | **0.9401** | 0.8074 | 0.7461 | 0.194 |

F1 từng lớp trên test:

| Lớp | MobileNetV3-S | ResNet18 | EffNet-Lite0 | ResNet50 |
|---|---|---|---|---|
| phone | 0.9204 | 0.8894 | 0.9408 | 0.9232 |
| eat_drink | 0.8659 | 0.8228 | 0.8723 | 0.9464 |
| reach_grooming | 0.8881 | 0.7933 | 0.8251 | 0.7609 |
| device_ops | 0.7669 | 0.8533 | 0.8270 | 0.8141 |
| normal | 0.6828 | 0.7231 | 0.8690 | 0.6457 |
| talk_passenger | 0.3905 | 0.4282 | 0.3818 | 0.3865 |

## Nhận xét
- **Val xếp hạng ngược với test.** Mô hình càng nặng thì val càng cao (ResNet50 0.940) nhưng test không tăng (0.746, thấp nhất). Chênh val − test tăng theo kích thước mô hình, từ 0.103 đến 0.194.
- Test của 4 mô hình chỉ cách nhau 0.04 (0.746 đến 0.786). Với test chỉ 4 tài xế và một seed, **không kết luận chắc mô hình nào hơn**, trừ nhận xét EfficientNet-Lite0 không thua mô hình nặng hơn nó 10 lần.
- Val chỉ có 4 tài xế và chọn epoch theo chính val nên điểm val lạc quan; ResNet50 val tụt 0.940 → 0.859 giữa epoch 5 và 7.
- `talk_passenger` yếu ở **mọi** mô hình (0.38–0.43), nên nguyên nhân nằm ở dữ liệu hoặc nhãn, không phải do chọn kiến trúc. Chưa xem confusion matrix nên chưa biết nó bị nhầm sang lớp nào.
- Chưa có số đo INT8, MB, độ trễ nên chưa đánh giá được "cổng khả thi" của research question.
