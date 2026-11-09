# 1. Tổng quan và yêu cầu

## 1.1 Bài toán và bối cảnh

DriveFocus là **đồ án môn học**, không phải sản phẩm thương mại. Mục tiêu là chứng minh bằng thực nghiệm một thiết bị đơn giản, giá thấp, gắn thêm vào **ô tô cá nhân**, có thể tự phát hiện tài xế buồn ngủ hoặc mất tập trung và nhắc ngay tại chỗ, đồng thời đóng góp dữ liệu ẩn danh cho bản đồ giao thông và rủi ro.

Điểm cốt lõi về mặt kỹ thuật: **các quyết định quan trọng (nhắm mắt, buồn ngủ, mất tập trung, dùng điện thoại) do thuật toán tự thiết kế đưa ra**, trên nền các cảm biến thị giác phổ thông (tìm mặt, điểm mốc, bàn tay, tư thế đầu). Không dùng mô hình phân loại hành vi đã huấn luyện của `dds-edge` cho các quyết định đó.

Khó khăn chính:

- **Phải chạy tại chỗ.** Từ lúc nhắm mắt đến lúc có tiếng báo phải tính bằng phần trăm giây; không chờ được mạng di động.
- **Báo nhầm giết sản phẩm.** Chớp mắt, liếc gương, kính râm, dừng đèn đỏ đều không phải nguy hiểm.
- **Camera hướng vào người.** Phải giảm thu thập dữ liệu từ gốc.
- **Phần cứng hạn chế.** K230 có bộ tăng tốc AI nhưng bộ nhớ, công suất, nhiệt đều eo hẹp.

## 1.2 Người dùng

| Tác nhân | Nhu cầu |
|---|---|
| **Chủ xe / tài xế (cá nhân)** | Được nhắc đúng lúc, ít báo nhầm; xem lịch sử chuyến và sự kiện của mình; tin rằng video không bị gửi đi |
| Nhóm đồ án | Cấu hình ngưỡng, chạy giả lập, đo hiệu năng, trình diễn |
| Người xem bản đồ rủi ro | Dữ liệu tổng hợp theo đoạn đường và khung giờ, không định danh |

Vì người dùng là cá nhân nên **không có yêu cầu về quản lý đội xe, phân quyền theo tổ chức**. Mỗi thiết bị gắn với một tài khoản chủ xe.

## 1.3 Vì sao có yếu tố Big Data

Không phải cảnh báo trên xe mà là phần sau nó:

| Đặc trưng | Biểu hiện |
|---|---|
| Volume | Mỗi xe gửi 1 điểm GPS mỗi giây; nghìn xe là nghìn sự kiện mỗi giây (Traffic-SM đã đo ổn ở khoảng 1.000 tài xế trên một bản sao) |
| Velocity | Cảnh báo cục bộ tức thời; bản đồ tắc nghẽn và rủi ro có giá trị sau vài chục giây |
| Variety | GPS, sự kiện hành vi, sức khỏe thiết bị, tóm tắt chuyến, đồ thị đường, Parquet |
| Veracity | GPS nhiễu, thiết bị offline rồi gửi bù muộn, đồng hồ lệch, sự kiện trùng |
| Value | Khớp sự kiện nguy hiểm vào đoạn đường thật để tìm điểm nóng rủi ro; điều chỉnh độ nhạy theo ngữ cảnh |

## 1.4 Yêu cầu chức năng

| Mã | Yêu cầu |
|---|---|
| FR1 | Phát hiện nhắm mắt kéo dài, PERCLOS, ngáp, gục đầu, nhìn lệch đường, không thấy mặt, bằng thuật toán trên điểm mốc khuôn mặt (file 4) |
| FR2 | Phát hiện dùng điện thoại/uống nước/hút thuốc bằng luật hình học bàn tay–khuôn mặt và nhìn xuống kéo dài |
| FR3 | Chỉ cảnh báo khi xe đang chạy (GPS có hysteresis, IMU dự phòng) |
| FR4 | Bốn mức cảnh báo; chỉ mức 4 là báo động; **nhắm mắt liên tục 3 s là mức 4** |
| FR5 | Hiệu chỉnh theo từng tài xế đầu chuyến: độ mở mắt bình thường, tư thế đầu trung tính |
| FR6 | Hoạt động đầy đủ khi không có mạng; sự kiện vào hàng đợi cục bộ và gửi bù |
| FR7 | Gửi GPS tới Traffic-SM dưới mã chuyến đi ẩn danh theo định dạng `POST /v1/ingest` hiện có |
| FR8 | Gửi sự kiện cảnh báo, heartbeat, tóm tắt chuyến lên DF-Cloud |
| FR9 | Khớp sự kiện vào đoạn đường để tạo bản đồ rủi ro theo đoạn × giờ trong tuần |
| FR10 | Đẩy ngữ cảnh đường (giới hạn tốc độ, loại đường, mức tắc) về thiết bị; dùng được nhưng không phụ thuộc |
| FR11 | Trang cá nhân: lịch sử chuyến, sự kiện của chính mình, điểm lái an toàn của mình |
| FR12 | Chạy toàn bộ luồng bằng bản giả lập (webcam/video + GPX hoặc luồng từ simulator của Traffic-SM) khi chưa có phần cứng |
| FR13 | (Sau cùng) Cập nhật firmware và mô hình qua mạng có chữ ký |

## 1.5 Yêu cầu phi chức năng

Các con số là **mục tiêu đề xuất**, xác nhận bằng đo đạc ở P2 và P3.

| Mã | Yêu cầu | Mục tiêu khởi điểm |
|---|---|---|
| NFR1 | Độ trễ từ lúc vượt ngưỡng đến lúc phát cảnh báo | ≤ 300 ms (chưa đo) |
| NFR2 | Tốc độ xử lý khuôn mặt | ≥ 15 khung/giây (chưa đo) |
| NFR3 | Báo nhầm mức ≥ 3 trên video lái bình thường | Đo và báo cáo; mục tiêu ≤ 1 lần/10 giờ |
| NFR4 | Độ nhạy mức 4 trên kịch bản nhắm mắt có chủ ý ≥ 3 s | ≥ 95% |
| NFR5 | Hoạt động khi mất mạng | Toàn bộ cảnh báo cục bộ giữ nguyên |
| NFR6 | Độ trễ GPS → ClickHouse (qua Traffic-SM) | ~10 giây như đã đo ở Traffic-SM |
| NFR7 | Riêng tư | Không truyền video; mã chuyến ẩn danh ở Traffic-SM |
| NFR8 | Bảo mật (mTLS, ACL, RBAC, OTA ký) | **Làm sau cùng (P6)**, xem file 7; giai đoạn đầu chạy trong mạng LAN tin cậy |
| NFR9 | Tái lập | Phần đám mây dựng bằng Docker Compose như Traffic-SM; bộ golden traces cho thuật toán |

## 1.6 Phạm vi

**Trong phạm vi:**
- Thuật toán giám sát tài xế (file 4) trên bản giả lập, sau đó port sang K230.
- Đo đạc, đánh giá trên nhiều bộ dữ liệu (không chỉ State Farm) và dữ liệu tự quay.
- Đám mây tối thiểu: cổng thiết bị, kho sự kiện, khớp đoạn đường, dashboard.
- Tích hợp hai chiều với Traffic-SM (GPS lên, ngữ cảnh xuống).

**Ngoài phạm vi:**
- Chứng nhận an toàn ô tô, tiêu chuẩn sản phẩm. Đây là đồ án nên có thể dùng dữ liệu chưa lý tưởng; giới hạn được ghi trong báo cáo.
- Điều khiển xe, nhận diện danh tính khuôn mặt.
- Xe máy (kính bảo hiểm che mặt), quản lý đội xe.
- Cảnh báo va chạm phía trước, nhận diện làn đường, dự báo tắc nghẽn.

## 1.7 Rủi ro chính

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Điểm mốc K230 (106 điểm hoặc face mesh) khác MediaPipe, cần ánh xạ lại điểm mắt/môi | Cao | Lập bảng ánh xạ ở P1; so sánh đặc trưng PC và K230 trên cùng video |
| Ban đêm, kính râm, ngược sáng | Cao | Camera IR; cờ "mắt không quan sát được" thay vì suy đoán (file 4, 4.4.1) |
| Ngưỡng EAR, PERCLOS, góc đầu chưa khớp với camera đặt trên xe | Cao | Cấu hình tách khỏi mã; chỉnh bằng dữ liệu tự quay đúng góc lắp |
| Luật hình học điện thoại báo nhầm khi tay chạm mặt | Trung bình | Điều kiện thời lượng; loại trường hợp tay chạm mắt; đo precision/recall |
| Dữ liệu công khai không khớp miền triển khai | Trung bình (chấp nhận được với đồ án) | Dùng nhiều nguồn; ghi giới hạn trong báo cáo |
| Mô hình K230 không biên dịch được hoặc chậm hơn dự kiến | Trung bình | Dùng ngay các mô hình trong SDK K230 (đã chạy được trên KPU); thử sớm khi có board |
| Chưa có board K230 | Trung bình | P1 và P4 chạy hoàn toàn trên giả lập |
