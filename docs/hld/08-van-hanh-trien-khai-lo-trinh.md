# 8. Vận hành, triển khai và lộ trình

## 8.1 Các môi trường

| Môi trường | Thiết bị | Đám mây | Dữ liệu | Mục đích |
|---|---|---|---|---|
| `sim` | Bản giả lập trên laptop (webcam/video + GPX) | Docker Compose trên cùng máy | Mô phỏng + người tự nguyện | Phát triển thuật toán và luồng |
| `lab` | Board K230 trên bàn | Compose trên một máy chủ | Quay có đồng ý | Đo hiệu năng, port, hồi quy |
| `pilot` | K230 lắp trên vài xe thật | Cụm nhỏ, có phân vùng, mTLS thật | Dữ liệu thật, có đồng ý, chính sách lưu giữ | Chỉnh ngưỡng, đo báo nhầm |
| `prod` (ngoài phạm vi) | | | | |

Phần đám mây tái dùng cách tổ chức của Traffic-SM: Docker Compose chia profile. Đề xuất thêm profile `df` (device-gateway, MQTT broker, context-publisher, `risk_stream`) cạnh các profile `sim`, `analytics`, `batch` hiện có.

## 8.2 Kiểm thử

| Tầng | Cách kiểm | Tiêu chí |
|---|---|---|
| Đơn vị | Máy trạng thái, cổng chuyển động, hệ số tốc độ bằng chuỗi đặc trưng tổng hợp | Mọi đường chuyển trạng thái trong sơ đồ file 4 được phủ |
| Golden traces | Chuỗi đặc trưng thật + chuỗi sự kiện mong đợi, dùng cho cả bản Python và C++ | Hai bản cho cùng sự kiện |
| Mô hình | F1 theo tài xế, F1 sau nncase, so ONNX vs kmodel | Tụt F1 do biên dịch ≤ 2 điểm macro-F1 (giả định ban đầu của `dds-edge`, cần xác nhận) |
| Tích hợp đám mây | Thiết bị giả gửi sự kiện/GPS, kiểm trùng, kiểm thứ tự, kiểm ẩn danh hóa | Không có `device_id` trong Traffic-SM hay `df.events` |
| Chịu tải | Nhiều thiết bị giả + traffic nền từ `gps-simulator` | Độ trễ GPS→ClickHouse còn trong vùng đã đo |
| Chịu lỗi | Ngắt mạng, kill gateway/Kafka/Spark worker, gửi trùng | Không mất sự kiện, không nhân đôi, cảnh báo cục bộ không đổi |
| Bảo mật | Thiết bị giả không chứng chỉ, chứng chỉ bị thu hồi, ACL sai chủ, ingest tràn | Tất cả bị từ chối và ghi nhật ký |
| Thực địa | Lái thật nhiều giờ, ghi video và sự kiện, nhãn tay mẫu | Báo nhầm mức ≥ 3 ≤ 1 lần/10 giờ; độ nhạy theo kịch bản dàn dựng ≥ 95% |

Kịch bản dàn dựng nên làm ở nơi an toàn (xe đứng yên với mô phỏng tốc độ, hoặc phòng thí nghiệm), không bao giờ nhắm mắt thật khi lái.

## 8.3 Giám sát

Thiết bị (qua heartbeat, hiển thị trên Grafana):

| Chỉ số | Ngưỡng cảnh báo vận hành |
|---|---|
| Mất heartbeat khi ACC bật | > 3 phút |
| `fps_face` thấp | < 10 fps kéo dài |
| `temp_c` cao | > 75 °C |
| `eyes_observable_ratio` thấp | < 0,6 theo chuyến (kính râm, camera bẩn, góc lệch) |
| `queue_depth` tăng | Mất mạng kéo dài |
| `config_version`/`fw_version` lệch | Thiết bị chưa cập nhật |

Đám mây: độ trễ end-to-end, lag consumer, tốc độ vào theo topic, tin vào `df.dead-letter`, số thiết bị online, thất bại xác thực. Dùng lại Kafka UI, Spark UI và Grafana của Traffic-SM, thêm bảng điều khiển `df`.

Chất lượng cảnh báo (chỉ số sản phẩm quan trọng nhất): số sự kiện mức ≥ 3 trên 10 giờ lái; tỉ lệ sự kiện bị tài xế dùng nút tạm dừng ngay sau đó (chỉ báo gián tiếp của báo nhầm); phân bố mức theo giờ trong ngày.

## 8.4 Cập nhật qua mạng (OTA)

| Thành phần | Cơ chế |
|---|---|
| Firmware | Phân vùng A/B, kiểm chữ ký trước khi chuyển, tự rollback nếu không khởi động hoặc không gửi được heartbeat sau cập nhật |
| Mô hình `.kmodel` | Gói ký riêng kèm `model card` (dữ liệu huấn luyện, F1 sau biên dịch, ngày); thay nóng ở khoảng xe dừng |
| Cấu hình ngưỡng | JSON/YAML ký số, có `config_version`, áp dụng khi xe dừng |
| Triển khai | Theo đợt (1% → 10% → toàn bộ); dừng ngay nếu tỉ lệ lỗi tăng |
| Không cập nhật khi đang chạy | Chỉ tải về khi xe chuyển động, áp dụng khi dừng |

## 8.5 Mở rộng và chịu lỗi (đám mây)

Theo số đo của Traffic-SM (một broker, một bản Location Service, 12 CPU/16 GB): 300 và 1.000 tài xế chạy ổn (trễ khoảng 10 đến 11 giây), 3.000 tài xế nghẽn ở map matching.

| Hướng | Cách |
|---|---|
| Thêm thiết bị | Mỗi thiết bị khoảng 1 sự kiện GPS/giây vào Traffic-SM; theo dõi lag `gps.traces` |
| Nghẽn map matching | Nhiều bản sao Location Service chung consumer group (8 partition), nhiều GraphHopper; đã được ghi nhận ở Traffic-SM |
| device-gateway | Không trạng thái ngoài ánh xạ (đọc từ kho), nhân bản sau cân bằng tải |
| MQTT broker | Từ một nút (Mosquitto) sang cụm (EMQX, NanoMQ hoặc HiveMQ) khi vượt vài nghìn kết nối |
| Kafka | Thêm broker, tăng replication factor (hiện 1 ở Compose); bắt buộc cho pilot |
| ClickHouse | Một nút đủ cho demo; sao chép khi pilot |
| Mất một thành phần | Kafka giữ tin; thiết bị hàng đợi; consumer xử lý bù (at-least-once, loại trùng bằng `event_id` và `ReplacingMergeTree`) |

## 8.6 Lộ trình theo giai đoạn (đồ án 3)

**Tiến độ (09/11/2026):**

| GĐ | Trạng thái | Ghi chú |
|---|---|---|
| P0 | Xong | |
| P1 | **Xong phần lõi**, chưa thử webcam thật | Thuật toán, giả lập, demo chạy được; 50 bài kiểm thử đạt; đã thử trên video tổng hợp (mắt nhắm giả lập bằng cách phủ màu da). Máy phát triển không có webcam |
| P2 | Chưa | Chưa có NTHU-DDD, YawDD, DMD; ngưỡng hiện là khởi điểm |
| P3 | Chưa | Cần board K230 |
| P4 | **Một phần** | device-gateway, hàng đợi gửi bù, bảng ClickHouse đã làm; 20 kiểm thử đạt với ingest giả lập. Chưa chạy với Traffic-SM, ClickHouse và Kafka thật, chưa có Grafana |
| P5, P6 | Chưa | |


Thuật toán đi trước; bảo mật làm sau cùng. Mỗi giai đoạn có **cổng qua**.

| GĐ | Nội dung | Sản phẩm | Cổng qua |
|---|---|---|---|
| **P0** | Tài liệu HLD, khảo sát repo, chốt hợp đồng thông điệp | HLD này | Rà soát xong |
| **P1** | **Thuật toán trên PC (ưu tiên số 1)**: cảm biến bằng MediaPipe, EAR/MAR/PERCLOS, tư thế, hiệu chỉnh trung tính, ngân sách chú ý, luật bàn tay–mặt, cổng chuyển động, máy trạng thái 4 mức; bản giả lập webcam/video + GPX; dựng baseline từ e-candeloro để so sánh | `edge/core` (Python), golden traces | Chạy được đủ 4 mức trên video tự quay; nhắm mắt có chủ ý 3 s kích hoạt mức 4 |
| **P2** | **Đánh giá và chỉnh ngưỡng**: NTHU-DDD, YawDD, DMD, State Farm (luật hình học), video tự quay; ROC cho EAR, PERCLOS; thí nghiệm hệ số tốc độ bật/tắt | Bảng kết quả và đồ thị cho báo cáo | Có số đo cho từng bộ đo (file 4, 4.8) |
| **P3** | **Port sang K230**: chạy các mô hình SDK, lập bảng ánh xạ điểm mốc, đo fps/nhiệt/RAM/độ trễ, cài lại tầng quyết định (MicroPython rồi C++), golden traces khớp | Bảng đo hiệu năng K230 | NFR1, NFR2 đạt; golden traces trên chip khớp |
| **P4** | **Đám mây tối thiểu + Traffic-SM** (chưa bảo mật): MQTT, device-gateway Go, `df.events`, ClickHouse, Grafana; GPS vào Traffic-SM bằng `trip_id`; thiết bị giả nhiều luồng | `cloud/` Compose, dashboard | Đường GPS → matched → congestion chạy với thiết bị giả; không có `device_id` ở Traffic-SM |
| **P5** | **Ghép sâu và hoàn thiện đồ án**: `risk_stream`, bản đồ rủi ro, `context-publisher`, điều chỉnh mức bằng ngữ cảnh; trang cá nhân; báo cáo, demo | Báo cáo, video demo | Sự kiện khớp đúng đoạn đường trên kịch bản có đáp án; thiết bị chạy tốt khi tắt ngữ cảnh |
| **P6** | **Bảo mật (sau cùng, nếu còn thời gian)**: mTLS, ACL, API gateway, RBAC, OTA ký, chính sách lưu giữ (file 7) | Bản gia cố | Theo file 7 |

P1 và P4 chạy song song được vì dùng chung hợp đồng ở P0. Có thể thử chạy các mô hình SDK K230 sớm khi có board mà không chờ P2.

### Việc nên làm ngay

1. Clone `e-candeloro/driver-state-detection` vào thư mục riêng, chạy với webcam, lấy làm baseline so sánh.
2. Viết bộ đo EAR/PERCLOS/MAR và máy trạng thái 4 mức theo file 4 với dữ liệu giả lập (golden traces đầu tiên).
3. Quay video thử có chủ ý nhắm mắt 1, 2, 3, 4 s (xe đứng yên, tốc độ mô phỏng) để kiểm ngưỡng.
4. Viết JSON Schema cho `df.event.v1`, `df.heartbeat.v1`, `df.trip.v1`, `df.context.v1`.

## 8.7 Rủi ro lịch trình

| Rủi ro | Hậu quả | Giảm thiểu |
|---|---|---|
| Chưa có board K230 | P3 bị chặn | P1, P2 không cần board; thử nncase sớm; đặt mua sớm |
| Thiếu dữ liệu đúng góc lắp | Ngưỡng và luật hình học kém chính xác | Thu dữ liệu tự quay có đồng ý ngay từ P1; nhãn tối thiểu |
| Chất lượng điểm mốc kém khi đeo kính/ban đêm | Báo nhầm hoặc bỏ sót | Cờ `eyes_observable`; thử camera IR sớm |
| Ngưỡng cảnh báo phải chỉnh nhiều | Kéo dài P5 | Cấu hình tách khỏi mã, golden traces để hồi quy |
| Mở rộng phạm vi sang an toàn chức năng | Mất kiểm soát | Giữ nguyên phạm vi "hỗ trợ" |
