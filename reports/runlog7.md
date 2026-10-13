# Runlog 7: dò learning rate và weight decay trên MobileNetV3-Small

3 lần chạy, mỗi lần đổi **một** tham số so với baseline `mnv3_clean` ([runlog 3](runlog3.md)). Dữ liệu, mô hình, 10 epoch, seed 42 giữ nguyên. Chạy bằng notebook Colab (`--workers 2`); baseline chạy trên Kaggle.

| Run | Lệnh khác baseline | Baseline |
|---|---|---|
| `mnv3_lr3e-4` | `--lr 3e-4` | lr 1e-3 |
| `mnv3_lr3e-3` | `--lr 3e-3` | lr 1e-3 |
| `mnv3_wd1e-2` | `--weight_decay 1e-2` | weight_decay 1e-4 |

## Mới so với runlog 6
- Thêm 3 cờ vào `train.py`: `--weight_decay`, `--label_smoothing`, `--class_weight` (mặc định giữ giá trị cũ). Lần này chỉ dùng `--lr` và `--weight_decay`.
- Chưa chạy `class_weight`, `label_smoothing`.

## Kết quả
| | Baseline (lr 1e-3) | lr 3e-4 | lr 3e-3 | wd 1e-2 |
|---|---|---|---|---|
| Val macro-F1 tốt nhất | 0.8720 (ep 9) | 0.7936 (ep 6) | 0.8946 (ep 9) | 0.8412 (ep 5) |
| Train loss epoch 10 | 0.4230 | 0.4284 | 0.4230 | 0.4231 |
| Test accuracy | 0.8380 | 0.8164 | 0.8090 | 0.8094 |
| **Test macro-F1** | **0.7524** | 0.7353 | 0.7443 | 0.7406 |

F1 từng lớp trên test:

| Lớp | Baseline | lr 3e-4 | lr 3e-3 | wd 1e-2 |
|---|---|---|---|---|
| phone | 0.9204 | 0.8963 | 0.9037 | 0.8548 |
| reach_grooming | 0.8881 | 0.8778 | 0.8071 | 0.8897 |
| eat_drink | 0.8659 | 0.8222 | 0.8902 | 0.7597 |
| device_ops | 0.7669 | 0.8295 | 0.8265 | 0.8145 |
| normal | 0.6828 | 0.5123 | 0.5680 | 0.6667 |
| **talk_passenger** | 0.3905 | **0.4734** | **0.4701** | **0.4583** |

## Nhận xét
- **Không cấu hình nào vượt baseline về test macro-F1** (thấp hơn 0.008 đến 0.017). Chênh lệch này nhỏ hơn mức nhiễu của test (4 tài xế, một seed), nên chưa kết luận được cấu hình nào kém hơn.
- `lr 3e-4` học chậm hơn: train loss epoch 10 vẫn cao (0.4284 so với 0.4230), val tốt nhất thấp nhất (0.7936).
- `lr 3e-3` có val cao nhất (0.8946) nhưng test không tăng, lại là chênh lệch val − test lớn (0.150, baseline 0.120).
- **`talk_passenger` tăng ở cả 3 cấu hình** (0.39 → 0.46 đến 0.47) **trong khi `normal` giảm** (0.68 → 0.51 đến 0.67). Giống như ranh giới giữa hai lớp này dịch chuyển, chứ không phải mô hình tốt hơn ở cả hai. Gợi ý nhầm lẫn giữa `normal` và `talk_passenger`, cần confusion matrix để xác nhận.
- Test chỉ có khoảng 225 ảnh `talk_passenger` và 237 ảnh `normal` (tính từ tỉ lệ trong tập test), nên F1 từng lớp dao động nhiều; mức tăng 0.07 của `talk_passenger` chưa chắc là thật.
- Kết luận tạm: giữ `lr 1e-3`, `weight_decay 1e-4`. Hướng tiếp theo: `class_weight sqrt`, và xem confusion matrix.
