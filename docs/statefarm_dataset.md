# Bộ dữ liệu State Farm Distracted Driver Detection

## 1. Tổng quan

| Mục | Nội dung |
|---|---|
| Nguồn | Kaggle competition *State Farm Distracted Driver Detection* (2016) |
| Bài toán | Phân loại ảnh (image classification) hành vi của tài xế: 10 lớp |
| Dữ liệu | Ảnh RGB chụp từ camera gắn trong xe (góc nhìn từ bên phải/trước tài xế), trích từ video |
| Kích thước ảnh | 640 × 480 px, JPEG |
| Số ảnh train | ~22.424 ảnh |
| Số ảnh test | ~79.726 ảnh (**không có nhãn**, chỉ dùng để nộp Kaggle) |
| Số tài xế (subject) | 26 người trong tập train (mã `p002`, `p012`, ... `p081`) |
| Giấy phép | Chỉ dùng theo điều khoản cuộc thi Kaggle (cần accept rules; ghi rõ trong báo cáo) |

> Lưu ý: số liệu trên là số liệu công bố của cuộc thi; hãy đếm lại trên bản tải về của bạn
> (`find data/raw/statefarm/imgs/train -name "*.jpg" | wc -l`).

## 2. Cấu trúc thư mục (cách gán nhãn bằng thư mục)

Nhãn của State Farm **được mã hoá bằng tên thư mục chứa ảnh**: ảnh nằm trong thư mục `cX` thì có nhãn `cX`.
Đây là kiểu *folder-per-class* (cùng kiểu với `torchvision.datasets.ImageFolder`).

```
data/raw/statefarm/
├── driver_imgs_list.csv        # bảng map: subject, classname, img
├── sample_submission.csv       # mẫu file nộp Kaggle
└── imgs/
    ├── train/
    │   ├── c0/  img_xxxxx.jpg  ...   # safe driving
    │   ├── c1/  ...                  # texting - right
    │   ├── c2/  ...                  # talking on the phone - right
    │   ├── c3/  ...                  # texting - left
    │   ├── c4/  ...                  # talking on the phone - left
    │   ├── c5/  ...                  # operating the radio
    │   ├── c6/  ...                  # drinking
    │   ├── c7/  ...                  # reaching behind
    │   ├── c8/  ...                  # hair and makeup
    │   └── c9/  ...                  # talking to passenger
    └── test/
        └── img_xxxxx.jpg ...         # không nhãn
```

### Bảng nhãn gốc (10 lớp)

| Nhãn (thư mục) | Hành vi (EN) | Hành vi (VI) | Phân loại |
|---|---|---|---|
| `c0` | Safe driving | Lái xe an toàn | Bình thường |
| `c1` | Texting – right | Nhắn tin bằng tay phải | Điện thoại |
| `c2` | Talking on the phone – right | Nghe/gọi điện bằng tay phải | Điện thoại |
| `c3` | Texting – left | Nhắn tin bằng tay trái | Điện thoại |
| `c4` | Talking on the phone – left | Nghe/gọi điện bằng tay trái | Điện thoại |
| `c5` | Operating the radio | Thao tác radio/bảng điều khiển | Thiết bị trong xe |
| `c6` | Drinking | Uống nước | Ăn uống |
| `c7` | Reaching behind | Với ra phía sau | Mất tập trung khác |
| `c8` | Hair and makeup | Chải tóc / trang điểm | Mất tập trung khác |
| `c9` | Talking to passenger | Nói chuyện với hành khách | Mất tập trung khác |

### File `driver_imgs_list.csv`

Ngoài nhãn theo thư mục, file này cho biết **ai** là người trong ảnh – thông tin quan trọng để chia train/val.

| Cột | Ví dụ | Ý nghĩa |
|---|---|---|
| `subject` | `p002` | Mã tài xế |
| `classname` | `c0` | Nhãn lớp (trùng tên thư mục) |
| `img` | `img_44733.jpg` | Tên file ảnh |

## 3. Điểm cần lưu ý khi dùng

- **Rò rỉ dữ liệu theo người (subject leakage):** các ảnh của cùng một tài xế rất giống nhau (trích từ video liên tiếp).
  Nếu chia ngẫu nhiên theo ảnh thì val/test chứa cùng người với train → độ chính xác ảo.
  → Phải chia theo `subject` (xem `python -m dds_edge.dl.prepare_data`).
- **Phân bố lớp tương đối cân bằng** (~2.000–2.500 ảnh/lớp), nhưng số ảnh/tài xế không đều.
- **Không lật ngang (horizontal flip) khi augmentation:** lật ảnh làm đổi tay trái ↔ tay phải
  (`c1↔c3`, `c2↔c4`) → sai nhãn.
- Tập `test` của Kaggle không có nhãn; đánh giá cuối cùng cần giữ riêng một nhóm tài xế làm test.

## 4. Cách gộp nhãn trong dự án (`src/dds_edge/dl/common.py`)

Dự án định nghĩa các "grouping" để thử nghiệm ảnh hưởng của việc gộp lớp:

| Grouping | Số lớp | Ánh xạ |
|---|---|---|
| `full10` | 10 | `c0`…`c9` giữ nguyên |
| `grouped6` | 6 | `normal`=c0; `phone`=c1–c4; `device_ops`=c5; `eat_drink`=c6; `reach_grooming`=c7+c8; `talk_passenger`=c9 |
| `grouped5` | 5 | `normal`=c0; `phone`=c1–c4; `reach_other`=c5+c7+c8; `eat_drink`=c6; `talk_passenger`=c9 |

Việc gộp được thực hiện **trong code (mapping nhãn lúc load)**, không đổi cấu trúc thư mục gốc.
