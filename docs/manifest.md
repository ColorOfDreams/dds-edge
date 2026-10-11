# File manifest — tập quan trọng nhất để train

Mọi lần train, validate và test trong dự án đều đọc từ **một file CSV duy nhất** (gọi là *manifest*).
Ảnh thì nằm rải rác ở nhiều thư mục/nguồn; manifest là "bản đồ" nói cho chương trình biết:
ảnh nào, nhãn gì, thuộc tập nào, của ai, từ bộ dữ liệu nào.

Ví dụ `data/processed/manifest.csv`:

```csv
path,label,split,group,source,raw_label
raw/statefarm/imgs/train/c0/img_100026.jpg,normal,train,p002,statefarm,c0
raw/statefarm/imgs/train/c2/img_123.jpg,phone,val,p042,statefarm,c2
raw/rf_dms_1/images/000231.jpg,eat_drink,train,rf_s07,rf_dms_1,drinking
own_recordings/frames/s03/f_000412.jpg,phone,test,s03,own,texting_right
```

## 1. Vì sao cần manifest thay vì chỉ dùng cấu trúc thư mục?

Cách "nhãn = tên thư mục" (State Farm: `c0..c9`) chỉ đủ khi có **một** bộ dữ liệu, **một** cách đặt tên lớp
và **không** quan tâm ai là người trong ảnh. Dự án này vượt cả ba điều kiện đó:

| Vấn đề | Thư mục không giải quyết được | Manifest giải quyết bằng |
|---|---|---|
| Nhiều nguồn (State Farm, Roboflow, tự quay) đặt tên lớp khác nhau | Mỗi nguồn một kiểu tên | Cột `label` (chung) + `raw_label` (gốc) |
| Cần biết ảnh thuộc train/val/test | Phải copy/di chuyển file | Cột `split` — không đụng vào file ảnh |
| Cần chống rò rỉ dữ liệu theo người/buổi quay | Thư mục không biết ai là ai | Cột `group` |
| Báo cáo điểm riêng từng nguồn | Không biết ảnh từ đâu | Cột `source` |
| Đổi cách gộp nhãn (10 lớp → 6 lớp) | Phải xếp lại cả thư mục | Sửa mapping, sinh lại CSV |

Nguyên tắc: **ảnh gốc không bao giờ bị sửa/di chuyển; mọi quyết định (nhãn, chia tập) nằm trong manifest.**
Muốn đổi thí nghiệm thì tạo manifest mới, không chạm vào `data/raw/`.

## 2. Giải thích từng cột

| Cột | Nghĩa | Ví dụ | Vì sao tồn tại |
|---|---|---|---|
| `path` | Đường dẫn ảnh, tương đối so với thư mục `data/`, dùng dấu `/` | `raw/statefarm/imgs/train/c2/img_123.jpg` | Để chương trình mở đúng ảnh. Đường dẫn tương đối nên chạy được trên Windows, Linux và Colab |
| `label` | Nhãn **đã gộp** về bộ lớp chung, dạng chữ | `phone` | Đây là đáp án model học. Mọi nguồn phải dùng chung bộ giá trị này, nếu không không thể train chung hay so sánh |
| `split` | Ảnh thuộc tập nào: `train`, `val` hoặc `test` | `val` | Để train, chọn epoch và đánh giá đúng phần dữ liệu của mình |
| `group` | Đơn vị không được tách ra giữa các tập | `p042` (tài xế), `s03` (buổi quay) | Dùng lúc tạo cột `split`: mọi ảnh cùng group phải cùng một tập. Đây là cột chống rò rỉ dữ liệu |
| `source` | Ảnh đến từ bộ nào | `statefarm`, `rf_dms_1`, `own` | Để báo cáo điểm riêng từng nguồn (trong miền, ngoài miền, tự quay) và gán vai trò cho nguồn |
| `raw_label` | Nhãn gốc của nguồn, giữ nguyên | `c2` | Để truy vết và sửa ánh xạ nhãn sau này mà không phải xử lý lại dữ liệu từ đầu |

### 2.1 `path` — đường dẫn tương đối
- Luôn tính từ `data/`, ví dụ `raw/statefarm/...`. Khi load: `Path("data") / row.path`.
- Dùng `/` kể cả trên Windows (Python mở được bình thường). Không dùng `\` và **không** dùng đường dẫn tuyệt đối
  như `D:\work\...` vì sẽ hỏng khi chuyển sang máy khác hoặc Colab.
- Mỗi `path` phải là duy nhất (một dòng = một ảnh).

### 2.2 `label` — nhãn chung
- Là chuỗi chữ (`normal`, `phone`, `device_ops`…), không dùng số. Số (index) chỉ sinh ra ở bước train
  bằng cách sắp tên lớp theo thứ tự cố định.
- Bộ giá trị được định nghĩa một lần (xem `GROUPINGS` trong [common.py](../src/dds_edge/dl/common.py), ví dụ
  `grouped6`: `normal, phone, device_ops, eat_drink, reach_grooming, talk_passenger`).
- Vì sao chữ: dễ đọc, không lệch khi thêm/bớt lớp, và tên lớp xuất hiện thẳng trong báo cáo/confusion matrix.
- Mọi nguồn dữ liệu phải ánh xạ về **đúng** bộ này. Ảnh nào không ánh xạ được thì bỏ khỏi manifest
  (hoặc đưa vào lớp `other` nếu cố ý có lớp đó), không để giá trị lạ lọt vào.

### 2.3 `split` — train / val / test
| Giá trị | Dùng để | Quy tắc |
|---|---|---|
| `train` | Cập nhật trọng số model | Có thể augmentation |
| `val` | Chọn epoch tốt nhất, chỉnh siêu tham số, early stopping | Không augmentation; **được** nhìn nhiều lần |
| `test` | Báo cáo kết quả cuối cùng | Chỉ chạy **một lần** ở cuối; không dùng để chỉnh gì cả |

Chỉ nhận đúng ba giá trị này (chữ thường). Giá trị khác → lỗi, không đoán.

### 2.4 `group` — cột chống rò rỉ dữ liệu
Đây là cột tinh tế và quan trọng nhất.

**Rò rỉ dữ liệu (leakage) là gì?** Ảnh State Farm được trích từ video, nên hàng trăm ảnh của cùng một tài xế
gần như giống hệt nhau (cùng người, cùng áo, cùng ghế, chỉ khác vài khung hình). Nếu chia ngẫu nhiên theo ảnh,
ảnh "gần giống bản sao" của một ảnh val lại nằm trong train. Model chỉ cần *nhớ mặt/áo của người đó* là đoán đúng
→ độ chính xác val cao ảo, ra thực tế (người mới) thì tụt mạnh.

**Cách chống:** gom ảnh thành các *group* (đơn vị không thể tách), rồi chia theo group chứ không theo ảnh.
- State Farm: `group` = mã tài xế (`p002`, `p042`…) — lấy từ cột `subject` của `driver_imgs_list.csv`.
- Video tự quay: `group` = buổi quay / người quay (`s03`), vì các frame trong một video rất giống nhau.
- Nguồn khác (Roboflow…): dùng id người/video nếu có; nếu không có, mỗi video/chuỗi ảnh liên tiếp là một group;
  nếu hoàn toàn không biết thì coi cả nguồn là **một group** (và chỉ dùng làm tập test ngoài miền).

**Quy tắc bất biến:** mỗi `group` chỉ xuất hiện trong **đúng một** `split`. Kiểm tra bằng:
```python
assert (df.groupby("group")["split"].nunique() == 1).all()
```
Lưu ý: `group` phải **không trùng giữa các nguồn** (`p002` của State Farm khác `p002` của nguồn khác).
Nếu sợ trùng, thêm tiền tố nguồn: `sf_p002`, `rf_s07`.

### 2.5 `source` — nguồn dữ liệu
- Mỗi bộ dữ liệu một tên cố định: `statefarm`, `rf_dms_1`, `own`…
- Dùng để:
  1. **Báo cáo riêng từng nguồn**: accuracy/F1 trên State Farm test (*trong miền*), trên bộ ngoài (*ngoài miền*,
     đo khả năng tổng quát hoá), và trên video tự quay (*điều kiện thật*). Gộp chung thì mất thông tin này.
  2. **Gán vai trò**: ví dụ State Farm = train/val/test; Roboflow = chỉ test ngoài miền; `own` = test (và có thể fine-tune).
  3. Lọc nhanh: `df[df.source == "own"]`.
- Ba nhóm điểm số nên báo cáo: *in-domain* (State Farm), *out-of-domain* (nguồn ngoài), *own* (tự quay).

### 2.6 `raw_label` — nhãn gốc
- Giữ nguyên giá trị nguồn cung cấp (`c2`, `texting_right`, `drinking`…), không chuẩn hoá.
- Vì sao giữ: nếu sau này đổi ý về cách gộp (ví dụ tách `c5` khỏi `device_ops`, hoặc chuyển từ `grouped6` sang
  `full10`), chỉ cần sửa bảng ánh xạ rồi sinh lại cột `label` từ `raw_label` — **không phải duyệt lại ảnh**.
- Dùng để tìm lỗi: `df.groupby(["raw_label","label"]).size()` cho thấy ngay nhãn gốc nào bị ánh xạ sang đâu.
- Cặp (`source`, `raw_label`) mới là định danh đầy đủ của nhãn gốc, vì hai nguồn có thể cùng dùng chữ
  `drinking` hoặc `c1` với nghĩa khác nhau.

## 3. Quy trình sinh manifest

```
 nguồn thô                  bảng ánh xạ nhãn            chia theo group           manifest.csv
 (State Farm, RF, own)  ─►  (source, raw_label) → label ─►  gán split cho group  ─►  path,label,split,group,source,raw_label
```

1. **Quét mỗi nguồn** → tạo bảng có `path`, `source`, `raw_label`, `group`.
   - State Farm: đọc `driver_imgs_list.csv` (`subject` → `group`, `classname` → `raw_label`).
2. **Ánh xạ nhãn**: tra bảng `(source, raw_label) → label`. Ví dụ State Farm `c1,c2,c3,c4 → phone`.
3. **Chia tập theo group**: xáo trộn danh sách group bằng seed cố định (ví dụ 42), rồi lần lượt gán
   test / val / train theo tỉ lệ (ví dụ 15 / 15 / 70 % **số group**, không phải số ảnh).
   Nguồn chỉ dùng ngoài miền thì gán thẳng `split=test`.
4. **Kiểm tra** (dừng nếu sai):
   - mỗi `group` chỉ ở một `split`;
   - `split ∈ {train, val, test}`, `label` thuộc bộ lớp chung;
   - không có `path` trùng; file ảnh tồn tại (ít nhất lấy mẫu);
   - mọi lớp đều có mặt trong `train` và `val`.
5. **Ghi** `data/processed/manifest.csv` và in thống kê (số ảnh theo `split × label`, `split × source`).

> Hiện trạng code: [prepare_data.py](../src/dds_edge/dl/prepare_data.py) đã sinh đúng manifest 6 cột này
> (hiện hỗ trợ nguồn `statefarm`; thêm nguồn mới = thêm một hàm `scan_<nguồn>` trả về `path, group, source, raw_label`
> và bảng ánh xạ nhãn tương ứng). `label` được cố định lúc sinh manifest theo `--grouping`
> (mặc định `grouped6`); thí nghiệm `full10` dùng manifest riêng (`--grouping full10 --out processed/manifest_full10.csv`).
> `train.py` / `export_quantize.py` đọc manifest qua `--root data --manifest processed/manifest.csv`.

## 4. Cách dùng khi train

```python
import pandas as pd
from pathlib import Path

DATA = Path("data")
df = pd.read_csv(DATA / "processed" / "manifest.csv")

classes = sorted(df["label"].unique())              # thứ tự cố định → index 0..K-1
cls2idx = {c: i for i, c in enumerate(classes)}

train = df[df.split == "train"]
val   = df[df.split == "val"]
test  = df[df.split == "test"]

# trong Dataset.__getitem__:
#   img = Image.open(DATA / row.path).convert("RGB")
#   y   = cls2idx[row.label]
```

Đánh giá theo nguồn:
```python
for src, g in test.groupby("source"):
    print(src, accuracy(g))          # in-domain / out-of-domain / own
```

## 5. Quy tắc bắt buộc (checklist)
- [ ] Một dòng = một ảnh; `path` duy nhất, tương đối, dùng `/`.
- [ ] `label` chỉ nhận giá trị thuộc bộ lớp chung.
- [ ] `split` chỉ là `train` / `val` / `test`.
- [ ] Mỗi `group` nằm trong đúng một `split`; `group` không trùng giữa các nguồn.
- [ ] Giữ nguyên `raw_label`; mọi thay đổi nhãn đi qua bảng ánh xạ, không sửa tay trong CSV.
- [ ] Tạo manifest bằng seed cố định, commit script (không commit ảnh); ghi seed/phiên bản vào báo cáo.
- [ ] `test` chỉ dùng cuối cùng; không chỉnh siêu tham số theo kết quả `test`.

## 6. Lỗi thường gặp
| Lỗi | Hậu quả | Cách tránh |
|---|---|---|
| Chia ngẫu nhiên theo ảnh | Rò rỉ, val/test cao ảo | Chia theo `group` + assert |
| `group` của hai nguồn trùng tên | Hai người khác nhau bị coi là một (hoặc ngược lại) | Thêm tiền tố nguồn |
| Dùng đường dẫn tuyệt đối | Hỏng trên máy khác/Colab | Luôn tương đối với `data/` |
| Sửa trực tiếp `label` trong CSV | Không tái lập được | Sửa bảng ánh xạ, sinh lại từ `raw_label` |
| Chỉnh siêu tham số theo `test` | Số liệu test bị lạc quan | Chỉ dùng `val` để chọn |
| Chỉ báo một điểm tổng | Che mất yếu kém ngoài miền | Báo theo `source` |
| Lật ngang ảnh khi augmentation | Nhãn trái/phải sai | Không `HorizontalFlip` (xem [common.py](../src/dds_edge/dl/common.py)) |
