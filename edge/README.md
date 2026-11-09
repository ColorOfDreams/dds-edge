# DriveFocus edge

Thuật toán giám sát tài xế, bản giả lập trên PC và demo. Thiết kế ở [../docs/hld](../docs/hld/README.md), thuật toán ở [file 4](../docs/hld/04-thuat-toan-va-muc-canh-bao.md).

## Cài đặt (Windows, Python 3.11)

```powershell
cd drivefocus\edge
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[vision,dev]" -e ..\cloud
.\.venv\Scripts\python scripts\download_models.py      # tải face_landmarker.task, hand_landmarker.task
```

## Chạy demo

```powershell
# Webcam, tốc độ giả lập 50 km/h. --quick rút ngắn hiệu chỉnh (8 s) để thử trên bàn.
.\.venv\Scripts\python -m drivefocus.demo --quick

# Video, không cửa sổ, ghi sự kiện và chuỗi đặc trưng
.\.venv\Scripts\python -m drivefocus.demo --source clip.mp4 --quick --no-window --mute `
    --events-out out\events.jsonl --trace-out out\trace.jsonl

# Có cửa sổ, tệp video được phát đúng tốc độ thật; thêm --fast để xử lý nhanh nhất có thể
.\.venv\Scripts\python -m drivefocus.demo --source clip.mp4 --quick

# Phát lại chuỗi đặc trưng (kết quả xác định)
.\.venv\Scripts\python -m drivefocus.replay out\trace.jsonl --quick
```

Phím trong cửa sổ: `w`/`s` tăng giảm tốc độ giả lập 10 km/h, `space` dừng/chạy, `c` hiệu chỉnh ngay (EAR mắt mở và tư thế đầu trung tính từ vài giây gần nhất), `m` tắt/bật còi, `g` bật/tắt cờ hướng nhìn, `q` thoát.

Cách thử các mức (xe đang "chạy" 50 km/h, đã hiệu chỉnh): nhắm mắt 0,5 s → mức 1, 1 s → mức 2, 2 s → mức 3, **3 s → mức 4**; quay đầu sang bên hoặc cúi xuống 1,5 s trở lên → mức 1 rồi leo thang theo ngân sách chú ý; đưa tay lên tai hoặc miệng ≥ 1,5 s → điện thoại/uống nước; nhấn `space` để dừng xe thì mọi cảnh báo tắt (sau 5 s giữ trạng thái).

## Nối với DF-Cloud và Traffic-SM

```powershell
.\.venv\Scripts\python -m drivefocus_cloud.mock_ingest --port 18080            # thay Traffic-SM khi chưa có Docker
.\.venv\Scripts\python -m drivefocus_cloud.gateway --port 18099 --ingest-url http://127.0.0.1:18080/v1/ingest
.\.venv\Scripts\python -m drivefocus.demo --quick --route-csv ..\..\traffic-SM\data\gps-fake\fake_gps.csv `
    --driver-id 15 --gateway http://127.0.0.1:18099
```

Khi có Docker, chạy Traffic-SM thật (xem README của nó) và đổi `--ingest-url` thành `http://localhost:8080/v1/ingest`. Mất mạng thì dữ liệu nằm trong `out/outbox.jsonl` và được gửi bù ở lần chạy sau.

## Kiểm thử

```powershell
.\.venv\Scripts\python -m pytest -q          # 50 bài: thuật toán, golden trace, cảm biến (cần mô hình và ảnh mẫu)
cd ..\cloud; ..\edge\.venv\Scripts\python -m pytest -q     # 20 bài: gateway
```

Bài kiểm thử cảm biến cần `models/samples/portrait.jpg` (ảnh mẫu của MediaPipe, không commit) và tự bỏ qua nếu thiếu. Cập nhật golden trace có chủ đích: `UPDATE_GOLDEN=1 pytest tests/test_golden.py`.

## Cấu trúc

| Tệp | Vai trò |
|---|---|
| `src/drivefocus/default_config.yaml` | Mọi ngưỡng, có chú thích |
| `geometry.py` | EAR, MAR, tư thế đầu (ma trận MediaPipe và PnP) |
| `motion.py` | Cổng chuyển động |
| `estimators.py` | Nhắm mắt/PERCLOS, ngáp, tư thế, tay–mặt, ngân sách chú ý |
| `engine.py` | Gộp thành mức 0 đến 4, máy trạng thái, cắt sự kiện |
| `perception.py` | MediaPipe → số đo (chỉ là cảm biến) |
| `hal.py`, `osd.py`, `uplink.py` | Giả lập camera/GPS/còi, hiển thị, đường lên cloud |
| `demo.py`, `replay.py` | Ứng dụng demo, phát lại trace |

## Giới hạn đã biết (đọc trước khi tin số đo)

- **Chưa thử với webcam thật.** Máy phát triển không có camera. Đã thử trên ảnh mẫu và video tổng hợp (mắt nhắm giả lập bằng cách phủ màu da lên vùng mắt).
- **Mọi ngưỡng là khởi điểm**, chưa hiệu chỉnh bằng dữ liệu thật. Đặc biệt các ngưỡng tay–mặt (`near_ear_k`, `near_mouth_k`) và ngưỡng độ tối của mắt (`eye_dark_ratio`) mới được đo trên một ảnh.
- **Chưa chạy trên K230.** Tầng cảm biến là MediaPipe; trên chip phải thay bằng mô hình SDK K230 và lập bảng ánh xạ điểm mốc (file 11).
- Luật tay–mặt không thấy điện thoại; tay chạm mặt vẫn có thể báo nhầm.
- **Chưa chạy với Traffic-SM thật**, chỉ với ingest giả lập tái hiện quy tắc kiểm tra của nó. Chưa có bảo mật (P6).
- Còi dùng `winsound.Beep` (Windows); nơi khác chỉ phát chuông terminal.
