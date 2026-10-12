# Runlog 4: ResNet18 (`runs/resnet18_clean`)

**Lệnh:** `python -m dds_edge.dl.train --arch resnet18 --grouping grouped6 --manifest processed/sf_320x240/manifest.csv --name resnet18_clean`

## Mới so với runlog 3
- Chỉ đổi mô hình: MobileNetV3-Small → **ResNet18** (pretrained ImageNet, fine-tune toàn bộ). Dữ liệu và hyperparameter giữ nguyên.
- Số tham số **11.179.590** (gấp 7,3 lần), **1,81 tỉ MACs** (gấp 32,7 lần).

## Kết quả
| Epoch | Train loss | Val acc | Val macro-F1 |
|---|---|---|---|
| 1 | 0.5576 | 0.8670 | 0.8112 |
| 2 | 0.4580 | 0.8214 | 0.7549 |
| **3** | 0.4474 | **0.9325** | **0.9015** |
| 4 | 0.4335 | 0.9057 | 0.8344 |
| 5 | 0.4283 | 0.9223 | 0.8674 |
| 6 | 0.4261 | 0.9226 | 0.8689 |
| 7 | 0.4231 | 0.9298 | 0.8889 |
| 8 | 0.4228 | 0.9146 | 0.8497 |
| 9 | 0.4227 | 0.9267 | 0.8813 |
| 10 | 0.4224 | 0.9245 | 0.8773 |

Checkpoint chọn: epoch 3 (val F1 0.9015).

| | Runlog 3 (MobileNetV3-S) | **Runlog 4 (ResNet18)** |
|---|---|---|
| Val macro-F1 tốt nhất | 0.8720 | 0.9015 |
| Test accuracy | 0.8380 | 0.8067 |
| Test macro-F1 | 0.7524 | **0.7517** |

F1 từng lớp (test): phone 0.8894, device_ops 0.8533, eat_drink 0.8228, reach_grooming 0.7933, normal 0.7231, **talk_passenger 0.4282**.

## Nhận xét
- Val cao hơn MobileNetV3 nhưng **test gần như bằng** (0.7517 so với 0.7524), dù nặng hơn 33 lần về tính toán. Chênh val và test là 0.150 (MobileNetV3: 0.120).
- Epoch tốt nhất là epoch 3, rất sớm; val dao động mạnh sau đó.
- `talk_passenger` tốt nhất trong các mô hình đến lúc này (0.428), `reach_grooming` thấp hơn (0.793 so với 0.888).
