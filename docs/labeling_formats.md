# Các cách gán nhãn (labeling) dữ liệu ảnh/video phổ biến

Tài liệu tổng hợp các định dạng annotation đang được dùng rộng rãi trong Computer Vision, kèm ưu/nhược điểm
và cách chọn cho bài toán của dự án (phân loại hành vi tài xế).

## 1. Phân loại theo loại bài toán

| Bài toán | Nhãn mô tả gì | Ví dụ |
|---|---|---|
| Image classification | 1 (hoặc nhiều) nhãn cho cả ảnh | "tài xế đang dùng điện thoại" |
| Object detection | Hộp (bounding box) + nhãn cho từng vật thể | hộp quanh điện thoại, tay, mặt |
| Semantic segmentation | Nhãn cho **từng pixel** (không phân biệt instance) | vùng "người", "ghế" |
| Instance segmentation | Mask riêng cho từng vật thể | mask từng người |
| Keypoint / Pose | Toạ độ các điểm khớp | khuỷu tay, cổ tay, mắt, mũi |
| Video / temporal | Nhãn theo đoạn thời gian | "00:03–00:07 nhắn tin" |
| Multi-label | Nhiều nhãn cùng lúc cho một ảnh | vừa "uống nước" vừa "nhìn lệch" |

## 2. Các cách tổ chức nhãn (storage format)

### 2.1 Theo thư mục (Folder-per-class)
Nhãn = tên thư mục chứa ảnh. Dùng cho **classification**. Đây là cách State Farm sử dụng.

```
train/
  c0/ img_1.jpg ...
  c1/ img_2.jpg ...
```
- Ưu: đơn giản nhất, `torchvision.datasets.ImageFolder` / `tf.keras.utils.image_dataset_from_directory` đọc trực tiếp.
- Nhược: chỉ 1 nhãn/ảnh; không có vị trí; không chứa metadata (người, thời gian) → cần file phụ.

### 2.2 CSV / TSV (bảng)
Mỗi dòng là một ảnh (hoặc một đối tượng).
```csv
img,classname,subject
img_44733.jpg,c0,p002
img_72999.jpg,c1,p002
```
- Ưu: dễ mở bằng Excel/pandas, dễ gắn metadata (subject, split, độ tin cậy).
- Nhược: khó biểu diễn cấu trúc lồng nhau (nhiều box/ảnh, polygon). Với detection thường mỗi box một dòng.
- Dùng: classification, multi-label (cột one-hot), detection đơn giản (`filename,xmin,ymin,xmax,ymax,class`), TensorFlow Object Detection CSV.

### 2.3 JSON
Linh hoạt, lồng nhau được. Nhiều định dạng chuẩn dựa trên JSON.
```json
{
  "image": "img_44733.jpg",
  "label": "c0",
  "subject": "p002",
  "split": "train"
}
```
- Ưu: biểu diễn được mọi loại nhãn, dễ đọc bằng mọi ngôn ngữ.
- Nhược: không có schema chuẩn nếu tự tạo; file lớn khó mở/sửa tay.
- Biến thể: **JSONL** (mỗi dòng một JSON) – tiện stream, dùng nhiều cho LLM/VLM dataset.
V
### 2.4 XML
Mỗi ảnh một file XML. Cũ nhưng còn phổ biến (xem Pascal VOC bên dưới).

### 2.5 TXT theo ảnh
Mỗi ảnh một file `.txt` cùng tên (chuẩn YOLO).

### 2.6 Mask ảnh (PNG)
Nhãn segmentation lưu thành ảnh: giá trị pixel = id lớp (hoặc id instance).

### 2.7 Database / định dạng nhị phân
TFRecord, LMDB, Parquet, WebDataset (`.tar` shards), HDF5 – dùng khi dữ liệu rất lớn, cần đọc nhanh.
Không phải định dạng nhãn "nhìn được" mà là đóng gói để huấn luyện.

## 3. Các định dạng annotation chuẩn cho Object Detection

Tất cả cùng mô tả "hộp bao" nhưng **toạ độ khác nhau**; chuyển đổi sai là lỗi rất hay gặp.

| Định dạng | File | Toạ độ box | Chuẩn hoá? | Ghi chú |
|---|---|---|---|---|
| **Pascal VOC** | 1 `.xml`/ảnh | `xmin, ymin, xmax, ymax` (pixel) | Không | Góc trên-trái và dưới-phải |
| **COCO** | 1 `.json` cho cả tập | `[x, y, width, height]` (pixel) | Không | (x,y) là góc trên-trái; có segmentation, keypoints |
| **YOLO (Darknet/Ultralytics)** | 1 `.txt`/ảnh | `class x_center y_center w h` | Có (0–1) | Mỗi dòng một đối tượng |
| **TFOD CSV** | 1 `.csv` | `xmin, ymin, xmax, ymax` (pixel) | Không | Dùng với TensorFlow Object Detection |
| **LabelMe** | 1 `.json`/ảnh | polygon/rectangle/point | Không | Công cụ LabelMe |
| **CVAT XML/JSON** | 1 file cho cả job | box, polygon, polyline, point | Không | Xuất được sang nhiều chuẩn khác |
| **Open Images** | CSV | `XMin, XMax, YMin, YMax` | Có (0–1) | Thứ tự cột khác VOC |
| **KITTI** | 1 `.txt`/ảnh | 2D box + 3D box | Không | Dành cho xe tự lái |

### Ví dụ cùng một hộp (ảnh 640×480, hộp từ (100,50) đến (300,250), lớp `phone`=0)

```text
# Pascal VOC (.xml)
<object><name>phone</name>
  <bndbox><xmin>100</xmin><ymin>50</ymin><xmax>300</xmax><ymax>250</ymax></bndbox>
</object>

# COCO (.json)
{"image_id": 1, "category_id": 1, "bbox": [100, 50, 200, 200]}

# YOLO (.txt)  -> x_c=200/640, y_c=150/480, w=200/640, h=200/480
0 0.3125 0.3125 0.3125 0.4167
```

## 4. Chi tiết COCO (chuẩn phổ biến nhất)

Một file JSON với ba phần chính:
```json
{
  "images":      [{"id": 1, "file_name": "img_1.jpg", "width": 640, "height": 480}],
  "annotations": [{
      "id": 10, "image_id": 1, "category_id": 1,
      "bbox": [100, 50, 200, 200],
      "area": 40000, "iscrowd": 0,
      "segmentation": [[100,50, 300,50, 300,250, 100,250]],
      "keypoints": [x1,y1,v1, x2,y2,v2]
  }],
  "categories":  [{"id": 1, "name": "phone", "supercategory": "object"}]
}
```
- Dùng được cho detection, instance segmentation, keypoints, captioning.
- `iscrowd=1` dùng RLE cho mask nhóm.

## 5. Keypoint / Pose

- **COCO keypoints**: 17 điểm người, mỗi điểm `(x, y, v)`; `v=0` không gán nhãn, `1` bị che, `2` thấy rõ.
- **MediaPipe / OpenPose**: 21 điểm bàn tay, 33 điểm cơ thể, 468 điểm mặt – thường là *đầu ra của model*
  dùng để sinh đặc trưng, không phải nhãn thủ công.
- Hữu ích cho bài toán tài xế: vị trí tay so với vô-lăng/mặt, hướng đầu.

## 6. Nhãn cho Video

| Cách | Mô tả |
|---|---|
| Nhãn theo clip | Mỗi video/đoạn cắt sẵn có 1 nhãn (như Kinetics, 100-Driver) |
| Nhãn theo khoảng thời gian | `start, end, label` (CSV/JSON) – dùng cho temporal action localization (ActivityNet, AVA) |
| Nhãn theo frame | Mỗi frame một nhãn, thường nội suy giữa các keyframe |
| Tracking | Box + `track_id` xuyên frame (MOT Challenge, CVAT) |

Ví dụ CSV theo khoảng thời gian:
```csv
video,start_s,end_s,label
rec_01.mp4,0.0,3.2,normal
rec_01.mp4,3.2,7.8,texting_right
```

## 7. Công cụ gán nhãn phổ biến

| Công cụ | Loại | Xuất định dạng |
|---|---|---|
| **CVAT** | Web, mã nguồn mở, video tốt | COCO, VOC, YOLO, MOT, LabelMe… |
| **Label Studio** | Web, đa phương thức (ảnh/âm thanh/văn bản) | JSON, COCO, VOC, YOLO, CSV |
| **LabelImg** | Desktop, đơn giản (box) | VOC, YOLO |
| **LabelMe** | Desktop, polygon | LabelMe JSON → COCO/VOC |
| **Roboflow** | SaaS, quản lý dataset + augmentation | Hầu hết các chuẩn |
| **V7 / Labelbox / Scale AI / SuperAnnotate** | Thương mại, có QA và đội gán nhãn | JSON riêng + xuất COCO |
| **Supervisely** | Nền tảng đầy đủ | JSON riêng, COCO… |

Xu hướng hiện nay: **gán nhãn bán tự động** (model gợi ý, người sửa), ví dụ SAM (Segment Anything) trong
CVAT/Label Studio/Roboflow, hoặc pre-label bằng YOLO / Grounding DINO.

## 8. So sánh nhanh & cách chọn

| Nhu cầu | Nên dùng |
|---|---|
| Phân loại ảnh, 1 nhãn/ảnh | Folder-per-class (+ CSV metadata) |
| Phân loại nhiều nhãn | CSV one-hot hoặc JSON list |
| Detection, train bằng Ultralytics YOLO | YOLO txt |
| Detection/segmentation, dùng Detectron2/MMDetection/torchvision | COCO JSON |
| Dữ liệu cũ, framework cũ | Pascal VOC XML |
| Video hành động | CSV/JSON theo khoảng thời gian |
| Dataset rất lớn | WebDataset / TFRecord / Parquet |

### Áp dụng cho DDS-Edge
- State Farm: **folder-per-class + `driver_imgs_list.csv`** (đã đủ cho phân loại, chia theo subject).
- Nếu tự quay video (`data/own_recordings`): nên dùng **CSV theo khoảng thời gian** (`video,start_s,end_s,label,subject`),
  sau đó trích frame ra cấu trúc folder-per-class để dùng chung pipeline.
- Nếu sau này cần phát hiện điện thoại/tay (detection): gán box bằng CVAT, xuất **YOLO** (train) và/hoặc **COCO** (đánh giá).

## 9. Lỗi thường gặp
- Nhầm thứ tự/đơn vị toạ độ giữa VOC, COCO, YOLO (pixel vs chuẩn hoá, `xyxy` vs `xywh`, góc vs tâm).
- Chia train/val theo ảnh thay vì theo người/video → rò rỉ dữ liệu.
- Lật ảnh khi augmentation làm sai nhãn có tính hướng (trái/phải).
- Không thống nhất tên lớp/ID giữa các file (index bắt đầu từ 0 hay 1: COCO category thường từ 1, YOLO từ 0).
- Không ghi lại hướng dẫn gán nhãn (guideline) và độ đồng thuận giữa các người gán (inter-annotator agreement).
