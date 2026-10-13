# Runlog 8: chạy lại trên Colab, INT8 và phân tích lỗi

Chạy trên Colab T4, `--workers 2`, dữ liệu sạch `sf_320x240`, 10 epoch, seed 42, các tham số mặc định. INT8 đo trên CPU máy tính (ONNX Runtime, 1 luồng, batch 1, test 2.581 ảnh).

## Mới so với runlog 7
- Có `best.pt` và `predictions.csv` cho `effl0_clean`, `resnet18_clean`, `mnv3_ep20` (20 epoch).
- Chạy lượng tử hoá INT8 (static, minmax và percentile) và đo kích thước, độ trễ, FPS.
- Phân tích lỗi bằng `analyze.py` (confusion matrix, điểm từng tài xế, xem ảnh).

## Điểm F1 chạy lại (Colab) so với lần đầu (Kaggle)
| Mô hình | Kaggle (runlog 4, 5) | Colab (lần này) |
|---|---|---|
| EfficientNet-Lite0 | 0,786 | **0,815** |
| ResNet18 | 0,752 | **0,770** |
| MobileNetV3-Small, 20 epoch | 0,752 (10 epoch) | 0,768 |

Cùng cấu hình và seed nhưng khác phần cứng, điểm lệch 0,02 đến 0,03. Thứ hạng EfficientNet-Lite0 cao hơn ResNet18 giữ nguyên. Đây là bằng chứng về nhiễu giữa các lần chạy.

## Lượng tử hoá INT8 và tốc độ (CPU máy tính, 1 luồng)
| Mô hình | Tham số | MACs | FP32 MB → INT8 MB | FP32 FPS → INT8 FPS | F1 FP32 (ONNX) → F1 INT8 |
|---|---|---|---|---|---|
| EfficientNet-Lite0 | 3,38 M | 384 M | 13,47 → 3,80 (3,5×) | 122 → 195 (1,6×) | 0,8141 → **0,8142** |
| ResNet18 | 11,18 M | 1,81 G | 44,71 → 11,30 (4,0×) | 34 → 108 (3,1×) | 0,7710 → **0,7718** |
| MobileNetV3-Small (run `mnv3_lr3e-3`) | 1,52 M | 55 M | 6,11 → 1,88 (3,2×) | 605 → 435 | 0,7443 → **0,1444** |

- EfficientNet-Lite0 và ResNet18: INT8 **không làm giảm F1** (chênh dưới 0,002), nhỏ hơn 3,5 đến 4 lần, và nhanh hơn 1,6 đến 3,1 lần. Cách chọn khoảng giá trị percentile cho kết quả tương đương minmax.
- MobileNetV3-Small: INT8 làm F1 sập ở mọi biến thể đã thử (0,06 đến 0,27) và còn chậm hơn FP32 trên CPU này. Đo trên run `mnv3_lr3e-3` (cùng kiến trúc, không có `best.pt` của baseline).
- MobileNetV3-Small là mô hình nhanh nhất ở FP32 (605 FPS) nhưng **không qua cổng khả thi INT8**. EfficientNet-Lite0 vừa chính xác nhất vừa qua cổng: 195 FPS, 3,8 MB, F1 0,814.
- Nguyên nhân MobileNetV3 sập chưa kiểm chứng (nghi do hard-swish và khối SE; EfficientNet-Lite dùng ReLU6 vốn thiết kế cho lượng tử hoá).

## Phân tích lỗi (EfficientNet-Lite0, test)
- `talk_passenger`: precision 0,81 nhưng recall 0,28. **56% ảnh `talk_passenger` bị đoán là `reach_grooming`**, chỉ 7% bị đoán là `normal` (giả thuyết trước đây về `normal` là sai).
- Ảnh bị nhầm: nhiều ảnh có tay giơ lên (chỉnh gương, hoặc tay hành khách chen vào khung hình) nên giống `reach_grooming`; lớp c9 đa dạng về hình ảnh và có thể nhập nhằng nhãn.
- ResNet18: `talk_passenger` bị nhầm sang `reach_grooming` (33%) và `phone` (28%).
- Điểm từng tài xế (test, EfficientNet-Lite0): p035 acc 0,953; p042 0,877; p081 0,861; p050 0,813 (macro-F1 0,70). Mức khó khác nhau nhiều giữa các tài xế; ResNet18 trên p081 macro-F1 chỉ 0,55.

## Chưa có kết quả
`mnv3_cw_sqrt`, `mnv3_aug2`, `mnv3_ep50` chỉ có `best.pt` (không có `metrics.json`); `mnv3_clean`, `mnv3_aug2_cw` rỗng. Cần tải lại từ Drive sau khi train xong hẳn.
