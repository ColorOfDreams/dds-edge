# Runlog 5: EfficientNet-Lite0 (`runs/effl0_clean`)

**Lệnh:** `python -m dds_edge.dl.train --arch efficientnet_lite0 --grouping grouped6 --manifest processed/sf_320x240/manifest.csv --name effl0_clean`

## Mới so với runlog 4
- Chỉ đổi mô hình: **EfficientNet-Lite0** (timm, pretrained, fine-tune toàn bộ). Dữ liệu và hyperparameter giữ nguyên.
- Số tham số **3.378.694**, **384 triệu MACs** (khoảng 1/5 ResNet18, gấp 6,9 lần MobileNetV3-Small).

## Kết quả
| Epoch | Train loss | Val acc | Val macro-F1 |
|---|---|---|---|
| 1 | 0.6876 | 0.8645 | 0.8066 |
| 2 | 0.4581 | 0.8825 | 0.8087 |
| 3 | 0.4413 | 0.8996 | 0.8491 |
| 4 | 0.4346 | 0.9038 | 0.8412 |
| 5 | 0.4294 | 0.9182 | 0.8755 |
| **6** | 0.4276 | **0.9220** | **0.8892** |
| 7 | 0.4261 | 0.9182 | 0.8756 |
| 8 | 0.4254 | 0.9129 | 0.8698 |
| 9 | 0.4248 | 0.9126 | 0.8696 |
| 10 | 0.4245 | 0.9176 | 0.8754 |

Checkpoint chọn: epoch 6 (val F1 0.8892).

| | Runlog 3 (MobileNetV3-S) | Runlog 4 (ResNet18) | **Runlog 5 (EffNet-Lite0)** |
|---|---|---|---|
| Val macro-F1 tốt nhất | 0.8720 | 0.9015 | 0.8892 |
| Test accuracy | 0.8380 | 0.8067 | 0.8535 |
| Test macro-F1 | 0.7524 | 0.7517 | **0.7860** |

F1 từng lớp (test): phone 0.9408, eat_drink 0.8723, normal 0.8690, device_ops 0.8270, reach_grooming 0.8251, **talk_passenger 0.3818**.

## Nhận xét
- **Test macro-F1 cao nhất đến lúc này (0.786)**, trong khi nhẹ hơn ResNet18 khoảng 5 lần về tính toán. Chênh val và test nhỏ nhất (0.103).
- Khác biệt chủ yếu ở `normal` (0.869, so với 0.68 và 0.72 ở hai mô hình trước). `talk_passenger` vẫn thấp (0.382).
- Đây là một lần chạy, một seed, test có 4 tài xế, nên khoảng cách 0.03 giữa các mô hình chưa chắc chắn.
