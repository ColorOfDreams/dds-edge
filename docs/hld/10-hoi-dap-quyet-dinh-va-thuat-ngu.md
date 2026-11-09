# 10. Nhật ký quyết định, câu hỏi mở, hỏi đáp và thuật ngữ

## 10.1 Nhật ký quyết định

| # | Quyết định | Phương án đã cân nhắc | Lý do |
|---|---|---|---|
| D1 | Quyết định cảnh báo hoàn toàn trên thiết bị | Suy luận trên đám mây | Độ trễ, mất mạng, riêng tư |
| D2 | **Mọi quyết định quan trọng dùng thuật toán tự viết** trên điểm mốc/bàn tay/tư thế; không dùng mô hình phân loại của dds-edge | Huấn luyện bộ phân loại trạng thái đầu-cuối | Yêu cầu của đồ án; State Farm không có lớp nhắm mắt; thuật toán giải thích được và đo được |
| D3 | Mạng nơ-ron chỉ là cảm biến phổ thông (mặt, điểm mốc, tay, tư thế), lấy từ MediaPipe (PC) và SDK K230 | Tự huấn luyện cảm biến | Đã có sẵn bản chạy trên KPU; tập trung sức vào thuật toán |
| D4 | Dữ liệu từ **nhiều nguồn**, State Farm chỉ một phần | Chỉ State Farm | Mỗi bộ đo cần dữ liệu phù hợp; dữ liệu không hoàn hảo là chấp nhận được với đồ án, ghi giới hạn trong báo cáo |
| D5 | Cổng chuyển động bằng GPS có hysteresis, IMU dự phòng, ngưỡng 10 km/h | OBD-II/CAN | Đơn giản; trùng ngưỡng của openpilot |
| D6 | Bốn mức; chỉ mức 4 là báo động; **nhắm mắt liên tục 3 s là mức 4** (hệ số tốc độ là thí nghiệm tùy chọn, mặc định tắt) | Ngưỡng co theo tốc độ mặc định | Giữ đúng yêu cầu 3 s |
| D7 | Ngân sách chú ý (giảm nhanh, hồi chậm) cho họ mất tập trung | Reset cứng mỗi lần liếc đường | Bắt được người nhắn tin xen kẽ liếc đường (ý tưởng của openpilot) |
| D8 | Quan sát ba trạng thái, `KHÔNG BIẾT` không tính vào bộ đếm hay PERCLOS | Coi mất mặt là nhắm mắt | Tránh báo nhầm do không nhìn thấy mắt |
| D9 | MQTT cho thiết bị, Kafka ở đám mây | Thiết bị gọi thẳng HTTP | Chịu mạng di động, giữ nguyên trục của Traffic-SM |
| D10 | `driver_id` ở Traffic-SM là `trip_id` | `device_id` thật | Traffic-SM không cần biết tài xế |
| D11 | Khớp sự kiện vào đoạn đường bằng nối luồng với `gps.matched` | Map matching riêng | Tái dùng kết quả đã khớp |
| D12 | Ngữ cảnh đường chỉ điều chỉnh mức, không là điều kiện bắt buộc | Thiết bị phụ thuộc đám mây | An toàn khi mất mạng |
| D13 | Giả lập bằng lớp trừu tượng phần cứng + golden traces | Ứng dụng điện thoại riêng | Tránh hai bản thuật toán lệch nhau |
| D14 | **Bảo mật làm sau cùng (P6)**, chỉ giữ video cục bộ và `trip_id` ẩn danh từ đầu | Làm bảo mật trước | Theo yêu cầu: thuật toán và tích hợp là trọng tâm của đồ án |
| D15 | Ô tô cá nhân trước; không làm xe máy, đội xe | | Theo yêu cầu; xe máy bị kính bảo hiểm che mặt |

## 10.2 Câu hỏi còn mở

Đã chốt: xe mục tiêu là ô tô, người dùng cuối là cá nhân, ngưỡng nhắm mắt mức 4 là 3 s.

| # | Câu hỏi | Ảnh hưởng | Gợi ý |
|---|---|---|---|
| Q1 | Board K230 cụ thể và ngày có hàng? | Lịch P3 | P1, P2, P4 không cần board |
| Q2 | Bảng ánh xạ điểm mắt/môi của `face_landmark` (106) hoặc `face_mesh` | Chất lượng EAR/MAR trên K230 | Làm ở P1/P3 |
| Q3 | Camera đặt ở đâu trong cabin (taplo, cột A, gương) | Ngưỡng góc đầu | Quay thử vài vị trí ở P1 |
| Q4 | Điều khoản tải NTHU-DDD, DMD, MRL | Có dùng được không | Kiểm tra trước P2 |
| Q5 | Cấu trúc repo: submodule hay hai thư mục cạnh nhau? | Quản lý phiên bản | Hiện cả ba nằm cạnh nhau trong `bigdata_btl`; hai repo cũ có `.git` riêng và chưa được repo cha theo dõi |
| Q6 | Bật hay tắt hệ số tốc độ trong demo cuối? | Trình diễn | Mặc định tắt; so sánh trong báo cáo |
| Q7 | Có kết nối OBD-II lấy tốc độ chính xác hơn GPS không? | Chất lượng cổng chuyển động | Ngoài phạm vi |

## 10.3 Hỏi đáp thường gặp

**Vì sao không gửi video lên đám mây để xử lý mạnh hơn?** Độ trễ và mất mạng làm cảnh báo trễ hoặc không đến; video khuôn mặt là dữ liệu rất nhạy cảm; băng thông LTE tốn kém. Thiết bị đã đủ sức chạy các mô hình nhẹ này theo số đo của chip.

**Traffic-SM có thật sự cần cho cảnh báo không?** Không. Thiết bị hoạt động độc lập. Traffic-SM thêm hai thứ: bản đồ tắc nghẽn/rủi ro do cả đội xe đóng góp, và ngữ cảnh đường (giới hạn tốc độ, tắc) để chỉnh độ nhạy.

**Tại sao một xe đơn lẻ không đủ cho Traffic-SM?** Mức tắc nghẽn là tốc độ trung vị của nhiều xe trên một đoạn so với tốc độ chuẩn học từ nhiều xe. Một xe không phân biệt được "đường tắc" với "mình chạy chậm". Vì thế đội xe mới có ý nghĩa, và khi chưa đủ xe thật thì `gps-simulator` tạo traffic nền.

**Nhắm mắt 3 giây có quá muộn không?** Ở 50 km/h là khoảng 42 m. Vì vậy các mức thấp hơn (0,5 s, 1 s, 2 s) cảnh báo sớm, và mức 4 giữ đúng 3 giây ở tốc độ đô thị rồi co lại khi nhanh hơn.

**Tài xế chớp mắt và liếc gương thì sao?** Chớp mắt thường dưới nửa giây và liếc gương thường dưới 1 giây; mọi điều kiện đều cần thời lượng liên tục vượt ngưỡng.

**Kính râm thì sao?** Nếu không quan sát được mắt, thiết bị không suy đoán mắt nhắm; chỉ dùng tư thế đầu và hành vi, báo qua heartbeat. Camera IR 940 nm xuyên được một số loại kính nhưng không phải mọi kính râm.

**Thiết bị bị rút nguồn để né giám sát?** Khi ACC bật mà mất heartbeat quá 3 phút, hệ thống đám mây thông báo cho chủ xe (`DEVICE_TAMPER` nếu thiết bị kịp báo trước khi tắt).

**Có nhận diện tài xế là ai không?** Không. Không dùng vector khuôn mặt. Gắn tài xế với chuyến là việc của hệ quản trị (thẻ, ứng dụng) và nằm ở vùng hạn chế.

**Bảo mật thiết bị nếu bị lấy mất?** Khóa riêng sinh trên thiết bị, chứng chỉ có thể thu hồi ngay; hàng đợi cục bộ chỉ chứa số liệu và được mã hóa; không có ảnh.

**Khác biệt giữa `df.events` và `traffic.congestion`?** Cái đầu là sự kiện hành vi của từng chuyến; cái sau là trạng thái giao thông của từng đoạn đường. Hai thứ gặp nhau ở bước khớp đoạn đường.

## 10.4 Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| **DF-Edge / DF-Cloud** | Phần thiết bị / phần đám mây của DriveFocus |
| **K230** | Chip SoC của Kendryte, 2 lõi RISC-V, có KPU |
| **KPU** | Bộ tăng tốc suy luận mạng nơ-ron trên K230 |
| **nncase / kmodel** | Trình biên dịch mô hình của Kendryte / định dạng mô hình chạy trên KPU |
| **PTQ / INT8** | Lượng tử hóa sau huấn luyện / số nguyên 8 bit |
| **EAR** | Eye Aspect Ratio: tỉ số mở mắt |
| **MAR** | Mouth Aspect Ratio: tỉ số mở miệng |
| **PERCLOS** | Tỉ lệ thời gian mắt nhắm gần hoàn toàn trong một cửa sổ |
| **Điểm mốc (landmark)** | Các điểm đặc trưng trên khuôn mặt (mắt, miệng, mũi, viền mặt) |
| **Cổng chuyển động** | Logic chỉ bật cảnh báo khi xe đang chạy |
| **Hysteresis** | Ngưỡng vào khác ngưỡng ra để tránh nhấp nháy |
| **HAL** | Hardware Abstraction Layer: lớp trừu tượng phần cứng |
| **Golden trace** | Chuỗi đầu vào + đầu ra mong đợi cố định dùng để kiểm hồi quy |
| **OTA** | Cập nhật qua mạng |
| **mTLS** | TLS hai chiều: cả máy chủ lẫn khách xuất trình chứng chỉ |
| **ACL** | Danh sách kiểm soát truy cập |
| **RBAC** | Phân quyền theo vai trò |
| **STRIDE** | Khung phân loại đe dọa: Spoofing, Tampering, Repudiation, Information disclosure, DoS, Elevation of privilege |
| **`trip_id`** | Mã chuyến đi ẩn danh, thay cho định danh tài xế khi vào Traffic-SM |
| **`traversal_key`** | Khóa đoạn đường trong Traffic-SM |
| **Map matching** | Khớp chuỗi điểm GPS vào mạng đường |
| **Lambda (kiến trúc)** | Hai đường tính toán: nhanh (luồng) và chậm (batch) |
| **Dead-letter** | Topic lưu thông điệp không xử lý được |
| **ASOF/stream-stream join** | Nối hai luồng theo gần nhất về thời gian |
