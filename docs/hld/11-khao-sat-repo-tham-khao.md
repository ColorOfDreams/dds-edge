# 11. Khảo sát repo và nguồn tham khảo

Khảo sát thực hiện ngày 09/11/2026 bằng cách đọc mã và hỏi API GitHub, không chỉ dựa vào hai repo của đồ án. Số sao và ngày cập nhật là tại thời điểm đó. **Giấy phép là điều bắt buộc phải xác nhận lại trên repo gốc trước khi chép mã.** Nguyên tắc: học ý tưởng thoải mái, chỉ chép mã khi giấy phép cho phép và ghi nguồn.

## 11.1 Các repo đã kiểm tra

| Repo | Giấy phép | Sao | Cập nhật cuối | Vai trò trong DriveFocus |
|---|---|---|---|---|
| [commaai/openpilot](https://github.com/commaai/openpilot) | MIT | ~64 nghìn | 09/11/2026 | **Tham khảo chính cho logic chính sách giám sát**: ngân sách chú ý, hiệu chỉnh tư thế, ngưỡng tốc độ, xử lý kính râm |
| [e-candeloro/driver-state-detection](https://github.com/e-candeloro/driver-state-detection) | MIT | ~159 | 18/08/2026 | **Tham khảo chính cho các bộ đo**: EAR, PERCLOS trượt, ba trạng thái, PnP, gaze từ iris. Có kiểm thử. Dự án đồ án sinh viên, đã chuyển sang MediaPipe Tasks |
| [kendryte/k230_sdk](https://github.com/kendryte/k230_sdk) | BSD-2-Clause | ~280 | 12/09/2025 | **Nền tảng K230**: thư mục `src/reference/ai_poc` có `face_detection`, `face_landmark`, `face_mesh`, `face_pose`, `face_glasses`, `eye_gaze`, `distraction_reminder`, `dms_system`... |
| [kendryte/nncase](https://github.com/kendryte/nncase) | Apache-2.0 | ~900 | 17/07/2026 | Biên dịch mô hình ONNX/TFLite sang `.kmodel` cho KPU |
| [kendryte/k230_canmv](https://github.com/kendryte/k230_canmv) | không khai báo trên GitHub | ~109 | 14/09/2024 | Firmware MicroPython. **Lưu ý:** push cuối 2024 và không có giấy phép khai báo; tài liệu CanMV trên kendryte.com có phiên bản mới hơn, cần kiểm tra repo/firmware hiện hành |
| [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | Apache-2.0 | ~37,6 nghìn | 07/11/2026 | Face Landmarker 478 điểm (có mống mắt), Hands: làm cảm biến cho bản giả lập và làm chuẩn đối chiếu với K230 |
| [opencv/opencv](https://github.com/opencv/opencv) | Apache-2.0 | ~91 nghìn | 09/11/2026 | `solvePnP`, xử lý ảnh |
| [sametgundz/drivesafe](https://github.com/sametgundz/drivesafe) | không khai báo | ~9 | 16/11/2025 | Chỉ để **tham khảo ý tưởng** (có MAR, PERCLOS, ước lượng tư thế). Không có giấy phép nên không chép mã |
| [Ella475/Driver-Awareness-Monitoring](https://github.com/Ella475/Driver-Awareness-Monitoring) | MIT | ~1 | 05/05/2023 | Quá nhỏ, không dùng |

Nhận xét thẳng thắn về hệ sinh thái: tìm "driver monitoring system" trên GitHub cho ra rất nhiều dự án cỡ bài tập (0 đến vài sao, đa số cùng một công thức EAR + MediaPipe). Chất lượng đáng tham khảo tập trung ở ba nơi: **openpilot** (logic chính sách trưởng thành), **e-candeloro** (bộ đo sạch, có test), **SDK K230** (đường ống chạy trên chip đích).

## 11.2 Đã đọc được gì và rút ra gì

### openpilot (`selfdrive/monitoring/policy.py`)

Các điểm kiểm chứng trực tiếp từ mã:

- `_ALERT_MIN_SPEED = 2.8  # 10 km/h`, kèm tham chiếu văn bản EU `OJ:L_202501899`: chỉ cảnh báo từ 10 km/h trở lên.
- Cảnh báo bằng một đại lượng `awareness` giảm với bước `DT / ALERT_3_TIMEOUT`, các ngưỡng mức 1 và 2 tính là `1 − T1/T3` và `1 − T2/T3`. Hệ số hồi phục thay đổi giữa 1,25 và 5 tùy `awareness` đang thấp hay cao. Mốc thời gian hiện tại của chính sách thị giác là 5, 8 và 13 giây.
- Hiệu chỉnh tư thế đầu "tự học" khi xe chạy trên 13 m/s (khoảng 30 mph), cần ít nhất 60 giây dữ liệu hợp lệ, ghi nhớ ngắn khoảng 6 phút.
- Có ngưỡng tư thế riêng cho trạng thái chưa hiệu chỉnh, và ngưỡng hướng đầu được nới theo góc lái.
- Tín hiệu chớp mắt bị nhân với xác suất mắt hiện rõ và xác suất không đeo kính râm của mô hình; không đủ độ tin cậy thì chuyển cơ chế (quay lại cảm biến vô-lăng).
- Có khóa leo thang sau nhiều lần mức 3 hoặc không phản hồi.

Mô hình thị giác của openpilot là mạng nơ-ron của họ (xuất ra xác suất chớp, ngủ, điện thoại); chỉ **lớp chính sách** là thứ ta học. Ta không dùng mô hình đó.

### e-candeloro (`attention_scorer.py`, `eye_detector.py`)

- Mỗi quan sát có thể là `None` (không biết): bộ đếm giữ nguyên, PERCLOS bỏ khoảng đó. Bộ đếm suy giảm theo hàm mũ (`decay_factor^t`) thay vì reset cứng.
- PERCLOS trượt theo thời gian (tích phân giữa các mẫu), chỉ sẵn sàng khi cửa sổ đủ đầy và phần hợp lệ ≥ 80%.
- Mặc định: `EAR ≤ 0,15` là nhắm, nhắm 2 s là buồn ngủ, `gaze > 0,2` trong 2 s, góc đầu > 20° trong 2,5 s, PERCLOS ≥ 0,2 trong 60 s.
- EAR tính theo pixel vì tọa độ chuẩn hóa làm méo tỉ lệ.
- Nhược điểm cần lưu ý: dùng webcam đặt trước mặt, ngưỡng chưa kiểm chứng cho camera đặt ở taplo hoặc cột A; EAR dùng ngưỡng tuyệt đối không chuẩn hóa theo từng người.

### K230 SDK `ai_poc`

- `dms_system`: phát hiện mặt (RetinaFace 0.25-MobileNet, 5 điểm) và lòng bàn tay (YOLOv5 MobileNetV2), rồi **luật logic** cho hút thuốc/uống/gọi điện dựa trên khoảng cách và hướng tâm bàn tay so với tâm mặt, đếm số khung liên tiếp. Phát hiện được lỗi: so độ dài với **diện tích** (xem 4.4.6).
- `distraction_reminder`: phát hiện mặt + `face_pose`, cảnh báo khi góc roll/yaw/pitch lệch quá ngưỡng trong N khung. Thuật toán đơn giản hơn nhiều so với 4.5.
- `eye_gaze`: mô hình hướng nhìn; `face_glasses`: phân loại có kính hay không.
- Các demo đếm theo số khung, không theo thời gian thực.

## 11.3 Bộ dữ liệu

Tình trạng truy cập chưa được kiểm chứng đầy đủ; ghi rõ để người làm kiểm tra.

| Bộ dữ liệu | Dùng cho | Tình trạng đã biết |
|---|---|---|
| State Farm Distracted Driver (đã có) | Luật hình học điện thoại/uống nước; phân loại phụ | Kaggle, theo điều khoản cuộc thi |
| NTHU-DDD | Buồn ngủ, chớp chậm, ngáp, gật đầu (nhãn theo khung) | Truy cập qua phòng thí nghiệm CV của NTHU; điều khoản chưa xác nhận được |
| YawDD | Ngáp | [IEEE DataPort](https://ieee-dataport.org/open-access/yawdd-yawning-detection-dataset), mở, dùng cho nghiên cứu, cần tài khoản IEEE miễn phí; video không gắn nhãn khung |
| DMD (Driver Monitoring Dataset) | Phân tâm đa dạng, nhìn lệch, điện thoại | Chưa xác nhận được điều khoản; thường dành cho nghiên cứu, cần đăng ký |
| MRL Eye Dataset | Ảnh cận mắt mở/nhắm | Chưa xác nhận được điều khoản. Lưu ý ảnh cận không có điểm mốc mặt nên dùng hạn chế với EAR |
| Video tự quay có đồng ý | Chỉnh ngưỡng, kịch bản nhắm mắt 1/2/3/4 s, góc camera thật | Của chính nhóm |

## 11.4 Việc cần làm tiếp để hoàn tất khảo sát

1. Clone `e-candeloro/driver-state-detection` vào thư mục riêng, chạy thử với webcam để có điểm so sánh đầu tiên (không sửa trực tiếp).
2. Xem mã `face_landmark` và `face_mesh` trong SDK K230 để chốt bảng ánh xạ điểm mắt/môi (việc P1/P3).
3. Đọc `policy.py` của openpilot lần nữa ở đoạn `_update_events` và `_update_awareness` khi cài đặt ngân sách chú ý, để so khớp hành vi.
4. Xác nhận giấy phép và cách tải của NTHU-DDD, DMD, MRL.
5. Tìm thêm các hướng khác chưa khảo sát: nghiên cứu về PERCLOS ngưỡng, chuẩn Euro NCAP/EU về DDAW, và các bài báo về ngáp/gục đầu để bảo vệ ngưỡng trong báo cáo.
