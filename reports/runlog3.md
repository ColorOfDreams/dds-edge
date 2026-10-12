# Runlog 3: baseline MobileNetV3-Small trên dữ liệu đã làm sạch (`runs/mnv3_clean`)

**Lệnh:** `python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --manifest processed/sf_320x240/manifest.csv --name mnv3_clean`

## Mới so với runlog 2
**Dữ liệu** (đây là thay đổi chính, từ đây mọi runlog dùng dữ liệu này)
- Loại ảnh gần trùng (độ lệch pixel < 2 trên ảnh nhỏ 32×24 xám, trong cùng tài xế và lớp): 22.424 → **20.007** ảnh (bỏ 2.417, 10,8%). Áp dụng cho cả train, val, test.
- Resize về **320×240** (giữ tỉ lệ 4:3), JPEG 90. Lúc train vẫn thu về 224×224 như cũ.
- Cách chia tài xế giữ nguyên (18/4/4). Số ảnh: train 13.809, val 3.617, test 2.581.
- Mốc đoán `phone` trên test: acc 0.3871, macro-F1 0.0930.

**Code huấn luyện** (không đổi hyperparameter): `cudnn.benchmark`, `channels_last`, `persistent_workers`, batch val/test gấp đôi, `drop_last=True` cho train.

Mọi thứ khác giữ nguyên (xem [runlog1.md](runlog1.md)): AdamW lr 1e-3, 10 epoch, batch 64, cosine, label smoothing 0.1, pretrained, augmentation, seed 42.

## Kết quả
Chạy thử 1 epoch trên dữ liệu mới (`smoke`): val F1 0.7740, test acc 0.7722, test macro-F1 0.6565.

| Epoch | Train loss | Val acc | Val macro-F1 |
|---|---|---|---|
| 1 | 0.6129 | 0.7680 | 0.6483 |
| 2 | 0.4541 | 0.8043 | 0.7424 |
| 3 | 0.4406 | 0.8557 | 0.7362 |
| 4 | 0.4357 | 0.8056 | 0.6928 |
| 5 | 0.4296 | 0.8745 | 0.8274 |
| 6 | 0.4258 | 0.8637 | 0.7929 |
| 7 | 0.4244 | 0.8737 | 0.8292 |
| 8 | 0.4233 | 0.8889 | 0.8491 |
| **9** | 0.4232 | **0.9021** | **0.8720** |
| 10 | 0.4230 | 0.8980 | 0.8598 |

Checkpoint chọn: epoch 9. Số tham số 1.524.006; **55,5 triệu MACs**.

| | Runlog 2 (dữ liệu cũ) | **Runlog 3 (dữ liệu sạch)** |
|---|---|---|
| Val macro-F1 tốt nhất | 0.8464 | 0.8720 |
| Test accuracy | 0.8306 | 0.8380 |
| Test macro-F1 | 0.7636 | **0.7524** |

F1 từng lớp (test): phone 0.9204, reach_grooming 0.8881, eat_drink 0.8659, device_ops 0.7669, normal 0.6828, **talk_passenger 0.3905**.
(Runlog 2: phone 0.9026, reach_grooming 0.8922, eat_drink 0.8035, device_ops 0.8021, normal 0.8017, talk_passenger 0.3793.)

## Nhận xét
- Val/test đã đổi (bỏ ảnh trùng, ít ảnh hơn) nên **không so trực tiếp** với runlog 2. Test macro-F1 khác nhau 0.011 là trong phạm vi nhiễu.
- Val vẫn dao động mạnh giữa các epoch (epoch 4: 0.693, epoch 9: 0.872).
- `talk_passenger` vẫn yếu nhất (0.39); `normal` đổi nhiều nhất (0.80 → 0.68).
