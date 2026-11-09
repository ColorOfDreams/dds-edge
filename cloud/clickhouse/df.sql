-- Cơ sở dữ liệu DriveFocus. Chạy trên cùng ClickHouse của Traffic-SM:
--   docker exec -i traffic-system-clickhouse-1 clickhouse-client --user traffic --password traffic --multiquery < df.sql
-- Cùng phong cách với traffic-SM/clickhouse/init.sql: ReplacingMergeTree để gửi lại không nhân đôi.

CREATE DATABASE IF NOT EXISTS df;

-- Sự kiện cảnh báo. KHÔNG có device_id: chỉ có trip_id ẩn danh.
-- Ánh xạ trip_id -> device_id nằm riêng trong kho hạn chế của device-gateway (SQLite ở bản demo).
CREATE TABLE IF NOT EXISTS df.events
(
    schema          LowCardinality(String),
    event_id        String,
    trip_id         String,
    type            LowCardinality(String),
    level           UInt8,
    ts_start        DateTime64(3, 'UTC'),
    ts_end          DateTime64(3, 'UTC'),
    duration_ms     UInt32,
    distance_m      Float32,
    speed_kmh_avg   Float32,
    speed_kmh_max   Float32,
    lat             Nullable(Float64),
    lng             Nullable(Float64),
    eyes_observable Bool DEFAULT true,
    context_used    Nullable(String),
    fw_version      LowCardinality(String),
    config_version  UInt16,
    received_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(received_at)
PARTITION BY toDate(ts_start)
ORDER BY (trip_id, ts_start, event_id);

-- Tóm tắt theo chuyến, tính từ sự kiện.
CREATE VIEW IF NOT EXISTS df.trip_summary AS
SELECT
    trip_id,
    min(ts_start)                       AS first_event,
    max(ts_end)                         AS last_event,
    count()                             AS events,
    countIf(level >= 3)                 AS severe_events,
    countIf(level = 4)                  AS alarms,
    sumIf(duration_ms, type = 'EYES_CLOSED') / 1000 AS eyes_closed_s
FROM df.events FINAL
GROUP BY trip_id;

-- Sự kiện theo loại và mức trong 24 giờ gần nhất (cho Grafana).
CREATE VIEW IF NOT EXISTS df.events_24h AS
SELECT type, level, count() AS n
FROM df.events FINAL
WHERE ts_start > now() - INTERVAL 24 HOUR
GROUP BY type, level;
