"""Đo hiệu năng trên CPU máy phát triển: cảm biến MediaPipe, thuật toán quyết định, gateway.

Chạy KHI MÁY RẢNH (không chạy song song tiến trình khác) để số đo không bị nhiễu.
"""
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "report" / "results"


def cpu_name() -> str:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return out or platform.processor()
    except Exception:
        return platform.processor()


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    import cv2
    import mediapipe as mp
    from drivefocus.config import load_config, quick_demo_overrides
    from drivefocus.engine import DecisionEngine
    from drivefocus.perception import MediaPipeSensor
    from drivefocus.types import MotionObs

    cfg = load_config(overrides=quick_demo_overrides())
    sensor = MediaPipeSensor(cfg, ROOT / "edge" / "models")
    cap = cv2.VideoCapture(str(ROOT / "edge" / "out" / "synthetic.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    engine = DecisionEngine(cfg)
    t_sensor, t_engine = [], []
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = n / fps
        a = time.perf_counter()
        obs, _ = sensor.process(frame, t)
        b = time.perf_counter()
        engine.update(obs, MotionObs(t, speed_kmh=50.0))
        c = time.perf_counter()
        if n >= 10:
            t_sensor.append((b - a) * 1000)
            t_engine.append((c - b) * 1000)
        n += 1
    sensor.close()

    # thuật toán quyết định riêng: nhiều khung hơn để ổn định
    from drivefocus.types import FrameObs
    e2 = DecisionEngine(cfg)
    N = 60000
    t0 = time.perf_counter()
    for i in range(N):
        t = i / 15.0
        e2.update(FrameObs(t=t, face=True, ear=0.3, eyes_observable=True, mar=0.05, yaw=0.0, pitch=0.0, roll=0.0),
                  MotionObs(t, speed_kmh=50.0))
    engine_only = (time.perf_counter() - t0) / N * 1000

    # gateway: đổi 5000 điểm sang định dạng ingest
    from drivefocus_cloud.gateway import to_ingest_payload
    pts = [{"ts": 1793062800.0 + i, "lat": 10.7759 + i * 1e-5, "lng": 106.7058, "speed_mps": 8.0} for i in range(5000)]
    prev = None
    t0 = time.perf_counter()
    for p in pts:
        pl = to_ingest_payload(p, "trip", "car", prev)
        prev = {"lat": pl["lat"], "lng": pl["lng"], "ts": pl["timestamp"]}
    gw_s = time.perf_counter() - t0

    res = {
        "machine": {"cpu": cpu_name(), "os": platform.platform(), "python": platform.python_version(),
                    "mediapipe": mp.__version__, "opencv": cv2.__version__},
        "frames": len(t_sensor), "frame_size": [w, h],
        "sensor_ms": {"mean": statistics.mean(t_sensor), "median": statistics.median(t_sensor),
                      "p95": pct(t_sensor, 95), "max": max(t_sensor)},
        "engine_ms_in_loop": {"mean": statistics.mean(t_engine), "p95": pct(t_engine, 95)},
        "engine_only_ms": engine_only,
        "pipeline_fps": 1000.0 / (statistics.mean(t_sensor) + statistics.mean(t_engine)),
        "gateway_points_per_s": 5000 / gw_s,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bench.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
