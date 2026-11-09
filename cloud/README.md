# DriveFocus DF-Cloud (demo)

Phần đám mây tối thiểu của DriveFocus: **device-gateway** (stdlib, không phụ thuộc), bảng ClickHouse và một **ingest giả lập** thay Traffic-SM khi chưa có Docker. Thiết kế ở [../docs/hld](../docs/hld/README.md) (file 5 và 6).

| Thành phần | Việc |
|---|---|
| `drivefocus_cloud.gateway` | `POST /v1/gps`: đổi sang định dạng `POST /v1/ingest` của Traffic-SM, `driver_id = trip_id`, bỏ `device_id`. `POST /v1/events`: loại trùng theo `event_id`, bỏ `device_id`, ghi ClickHouse và JSONL. Ánh xạ trip→device nằm riêng trong SQLite. `GET /health` |
| `drivefocus_cloud.mock_ingest` | Tái hiện quy tắc `gps.Canonicalize` của Traffic-SM để chứng minh payload hợp lệ. **Không phải Traffic-SM** |
| `clickhouse/df.sql` | Bảng `df.events` và hai view |

```powershell
..\edge\.venv\Scripts\python -m drivefocus_cloud.mock_ingest --port 18080
..\edge\.venv\Scripts\python -m drivefocus_cloud.gateway --port 18099 --ingest-url http://127.0.0.1:18080/v1/ingest
# với ClickHouse của Traffic-SM:  --clickhouse-url http://localhost:8123  (cần chạy clickhouse/df.sql trước)
..\edge\.venv\Scripts\python -m pytest -q       # 20 bài
```

Chưa làm: xác thực, mTLS, giới hạn tốc độ (P6); Spark `risk_stream` và bản đồ rủi ro; `context-publisher`; Grafana; MQTT. Gateway hiện nhận HTTP trực tiếp từ thiết bị.
