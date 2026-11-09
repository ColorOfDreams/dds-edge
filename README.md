# DriveFocus

Đồ án môn học: thiết bị hỗ trợ lái xe thông minh cho **ô tô cá nhân**, chạy trên chip **Kendryte K230** (KPU khoảng 6 TOPS theo nhà sản xuất). Camera trong cabin theo dõi tài xế (buồn ngủ, mất tập trung, dùng điện thoại), **chỉ hoạt động khi xe đang chạy**, cảnh báo theo 4 mức, và chỉ báo động khẩn cấp ở mức nguy cấp nhất (nhắm mắt liên tục 3 giây). Thiết bị gửi GPS và sự kiện (không gửi video) lên đám mây, nơi **Traffic-SM** biến nhiều xe thành mạng cảm biến giao thông và trả lại ngữ cảnh đường.

## Trạng thái (09/11/2026)

| Phần | Trạng thái |
|---|---|
| Tài liệu HLD | [docs/hld](docs/hld/README.md), 12 file |
| Thuật toán + giả lập + demo (P1) | **Có**, [edge/](edge/README.md). 50 bài kiểm thử đạt; demo chạy ~35 fps trên CPU máy phát triển; thử trên video tổng hợp, **chưa thử webcam thật** |
| Đám mây tối thiểu (một phần P4) | **Có**, [cloud/](cloud/README.md). 20 bài đạt với ingest giả lập; **chưa chạy với Traffic-SM thật** |
| K230, đánh giá bằng bộ dữ liệu, risk_stream, bảo mật | Chưa |

Mọi ngưỡng và con số hiệu năng là giá trị khởi điểm, chưa hiệu chỉnh bằng dữ liệu thật.

> Bản v0.3, 09/11/2026. Đổi tên từ DriveGuard thành DriveFocus. Đã chốt: ô tô, người dùng cá nhân, ngưỡng 3 giây, thuật toán là trọng tâm, bảo mật làm sau cùng.

## Đọc ở đâu

Toàn bộ tài liệu nằm trong [docs/hld/](docs/hld/README.md). Phần thuật toán (trọng tâm) ở [file 4](docs/hld/04-thuat-toan-va-muc-canh-bao.md); khảo sát repo thật ở [file 11](docs/hld/11-khao-sat-repo-tham-khao.md); ý tưởng mở rộng ở [file 12](docs/hld/12-y-tuong-mo-rong.md); web ETA và chỉ đường ở [file 13](docs/hld/13-web-eta-dan-duong.md).

## Ba khối của hệ thống

| Khối | Nguồn gốc | Vai trò |
|---|---|---|
| **DF-Edge** (thiết bị K230) | Mới; cảm biến thị giác từ SDK K230 và MediaPipe | Thuật toán nhận diện trạng thái tài xế, cảnh báo cục bộ, không cần mạng |
| **DF-Cloud** (cổng thiết bị, sự kiện, trang cá nhân) | Mới | Nhận sự kiện, ẩn danh hóa, khớp đoạn đường, dashboard |
| **Traffic-SM** | Repo `traffic-SM` sẵn có | Nhận GPS nhiều xe, map matching, mức tắc nghẽn; trả ngữ cảnh đường cho thiết bị |

`dds-edge` đóng vai trò nguồn dữ liệu đánh giá, công cụ đo và khung demo; mô hình phân loại của nó không nằm trên đường quyết định.

## Nguyên tắc xuyên suốt

1. **Quyết định bằng thuật toán.** Mạng nơ-ron chỉ là cảm biến phổ thông (mặt, điểm mốc, tay, tư thế); mọi ngưỡng và logic cảnh báo do nhóm viết và đo được.
2. **An toàn trước, mạng sau.** Cảnh báo quyết định hoàn toàn trên thiết bị, mất mạng vẫn chạy.
3. **Không suy diễn khi không thấy.** Không nhìn thấy mắt thì trạng thái là `KHÔNG BIẾT`, không phải "nhắm mắt".
4. **Video không rời thiết bị.** Traffic-SM chỉ thấy mã chuyến ẩn danh.
5. **Mô phỏng trước, phần cứng sau.** Cùng lõi thuật toán chạy trên laptop trước khi có board K230.
6. **Bảo mật làm sau cùng (P6).**
