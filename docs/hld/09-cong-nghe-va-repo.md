# 9. Công nghệ, repo và bộ dữ liệu

Cột "giấy phép" ghi theo hiểu biết tại thời điểm viết; **phải kiểm tra lại trên repo gốc** trước khi dùng, nhất là cho mục đích thương mại. Một số dự án đã đổi giấy phép trong vài năm qua.

## 9.1 Thiết bị biên K230

| Hạng mục | Công nghệ / repo | Ghi chú |
|---|---|---|
| SDK chính | [kendryte/k230_sdk](https://github.com/kendryte/k230_sdk) | Chứa mã demo AI (`src/reference/ai_poc`) và `.kmodel` mẫu; cấu trúc thư mục thay đổi theo phiên bản, đối chiếu đúng bản SDK |
| Firmware MicroPython | [kendryte/k230_canmv](https://github.com/kendryte/k230_canmv) (CanMV) | Nguyên mẫu nhanh |
| Trình biên dịch mô hình | [kendryte/nncase](https://github.com/kendryte/nncase) | ONNX/TFLite → `.kmodel`, lượng tử hóa INT8/INT16. Kiểm tra hỗ trợ toán tử từng lớp |
| Demo tham khảo | `dms_system`, `distraction_reminder`, `face_landmark`, `face_pose` trong AI demo của SDK | Dùng để học luồng pipeline và tiền/hậu xử lý, không coi là thuật toán cuối |
| Tài liệu | [K230 Product Brief](https://www.kendryte.com/k230/en/dev/K230_brief_datasheet.html), tài liệu SDK ở kendryte.com | |
| Ngôn ngữ | C++17 (lõi), MicroPython (nguyên mẫu) | |
| MQTT trên thiết bị | Thư viện MQTT nhỏ (ví dụ Eclipse Paho C/embedded hoặc tương đương) | Chạy ở lõi Linux |
| Lưu hàng đợi | SQLite hoặc file nối đuôi có mã hóa | |

## 9.2 Mô hình thị giác và thuật toán

Mạng nơ-ron chỉ là cảm biến phổ thông; **không huấn luyện mô hình quyết định**. Chi tiết khảo sát repo ở [file 11](11-khao-sat-repo-tham-khao.md).

| Hạng mục | Công nghệ | Ghi chú |
|---|---|---|
| Điểm mốc, bàn tay (PC / giả lập) | [MediaPipe](https://github.com/google-ai-edge/mediapipe) Face Landmarker (478 điểm, có mống mắt) và Hands | Apache-2.0 |
| Điểm mốc, bàn tay, tư thế (K230) | `face_detection`, `face_landmark`, `face_mesh`, `face_pose`, `eye_gaze`, `face_glasses`, phát hiện lòng bàn tay trong `dms_system` | BSD-2-Clause (SDK) |
| Tư thế đầu | `cv2.solvePnP` ([OpenCV](https://github.com/opencv/opencv), Apache-2.0) | |
| Tham khảo thuật toán | [e-candeloro/driver-state-detection](https://github.com/e-candeloro/driver-state-detection) (MIT), [commaai/openpilot](https://github.com/commaai/openpilot) (MIT) | Học ý tưởng; chép mã thì ghi nguồn |
| Biên dịch KPU (nếu cần mô hình tự xuất) | nncase | Chủ yếu dùng `.kmodel` có sẵn trong SDK |
| Tái dùng từ dds-edge | ONNX Runtime để đo, `web_demo.py`, dữ liệu State Farm | Mô hình phân loại chỉ là kênh phụ tùy chọn |

## 9.3 Truyền thông và cổng thiết bị

| Hạng mục | Lựa chọn đề xuất | Phương án thay thế / ghi chú |
|---|---|---|
| Giao thức thiết bị | MQTT 3.1.1/5 qua TLS | HTTPS lô cho GPS nếu muốn đơn giản |
| MQTT broker (demo) | [Eclipse Mosquitto](https://github.com/eclipse-mosquitto/mosquitto) | Giấy phép EPL/EDL. Hỗ trợ TLS, ACL |
| MQTT broker (mở rộng) | EMQX, NanoMQ, HiveMQ CE | EMQX có giấy phép nguồn mở có điều kiện từ các bản gần đây, **kiểm tra trước**; NanoMQ và HiveMQ CE là phương án khác |
| device-gateway | Go (cùng ngôn ngữ với Location Service để dùng lại kiểu `gps.CanonicalEvent`) | Mã tự viết |
| API gateway | Envoy, Traefik hoặc NGINX | Giới hạn tốc độ, TLS, xác thực |
| Hàng đợi / bus | Apache Kafka (đã có, `apache/kafka:4.3.1`) | Thêm SASL_SSL và ACL |
| Schema | JSON Schema (khởi đầu), Protobuf nếu cần gọn hơn | |

## 9.4 Xử lý luồng, lưu trữ và hiển thị (tái dùng Traffic-SM)

| Hạng mục | Công nghệ | Trạng thái |
|---|---|---|
| Map matching | GraphHopper (fork `ColorOfDreams/graphhopper` là submodule) | Dùng nguyên |
| Dữ liệu không gian | Tile38 `1.38.0` | Dùng nguyên |
| Location Service | Go + Gin | Dùng nguyên, đặt sau gateway |
| Xử lý luồng/batch | Spark Structured Streaming | Dùng nguyên; thêm `risk_stream.py` |
| Kho phân tích | ClickHouse | Dùng nguyên; thêm cơ sở dữ liệu `df` |
| Dashboard | Grafana | Bật xác thực; thêm bảng điều khiển |
| Data lake | Parquet | Thêm chính sách xóa/ẩn danh hóa |

## 9.5 Bảo mật và vận hành (làm sau cùng, P6)

| Hạng mục | Lựa chọn đề xuất | Ghi chú giấy phép |
|---|---|---|
| CA cho thiết bị | [smallstep step-ca](https://github.com/smallstep/certificates) | Apache-2.0 |
| IdP / SSO | Keycloak | Apache-2.0 |
| Kho bí mật | OpenBao, hoặc HashiCorp Vault, hoặc SOPS cho demo | Vault chuyển sang giấy phép BSL từ 2023; OpenBao là nhánh mã nguồn mở |
| VPN quản trị | WireGuard | |
| Kho đối tượng (ảnh bằng chứng, nếu bật) | MinIO hoặc S3 tương thích | MinIO dùng AGPLv3: cân nhắc khi phân phối |
| Giám sát | Prometheus + Grafana + OpenTelemetry | Grafana dùng AGPLv3 |
| Quét lỗ hổng/SBOM | Trivy, Syft | |
| Triển khai | Docker Compose (demo); Kubernetes (pilot trở đi) | |
| CI | GitHub Actions: build, test, quét, ký gói OTA | |

## 9.6 Bộ dữ liệu

Danh sách đầy đủ kèm tình trạng truy cập ở [file 11, mục 11.3](11-khao-sat-repo-tham-khao.md). Dùng nhiều nguồn bổ trợ, State Farm chỉ là một phần: **NTHU-DDD** (buồn ngủ), **YawDD** (ngáp), **DMD** (phân tâm), **State Farm** (điện thoại/uống nước), **MRL Eye** (mắt, dùng hạn chế), **video tự quay có đồng ý** (chỉnh ngưỡng đúng góc lắp). Dữ liệu OpenStreetMap Việt Nam (Geofabrik, ODbL) cho đồ thị đường: ghi công và chia sẻ tương tự cho dữ liệu dẫn xuất.

## 9.7 Kiểm tra giấy phép: quy trình

1. Lập SBOM (Syft) cho mọi ảnh container và gói thiết bị.
2. Lập bảng giấy phép theo từng phụ thuộc; đánh dấu AGPL, BSL/SSPL, "chỉ nghiên cứu", "phi thương mại".
3. Chặn trong CI bất kỳ giấy phép nằm ngoài danh sách cho phép.
4. Ghi vào `model card` nguồn dữ liệu huấn luyện và giấy phép.
