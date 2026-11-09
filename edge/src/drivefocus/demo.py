"""Demo DriveFocus trên PC: webcam hoặc video + tốc độ giả lập + còi + (tùy chọn) đẩy lên DF-Cloud.

Ví dụ:
    python -m drivefocus.demo --quick                      # webcam 0, tốc độ giả lập 50 km/h
    python -m drivefocus.demo --source clip.mp4 --no-window --events-out out/events.jsonl
    python -m drivefocus.demo --quick --route-csv ../../traffic-SM/data/gps-fake/fake_gps.csv \
        --driver-id 12 --gateway http://localhost:8099
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import load_config, quick_demo_overrides
from .engine import DecisionEngine
from .hal import ManualSpeed, RouteSource, SoundActuator, VideoSource
from .replay import write_trace  # noqa: F401  (xuất cho tiện)
from .types import FrameObs, MotionObs


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="DriveFocus edge demo")
    ap.add_argument("--source", default="0", help="chỉ số webcam hoặc đường dẫn video")
    ap.add_argument("--config", help="YAML ghi đè cấu hình mặc định")
    ap.add_argument("--quick", action="store_true", help="rút ngắn hiệu chỉnh để thử trên bàn")
    ap.add_argument("--speed", type=float, default=50.0, help="tốc độ giả lập ban đầu (km/h)")
    ap.add_argument("--route-csv", help="phát lại tuyến GPS (CSV của Traffic-SM hoặc t,lat,lng,speed_kmh)")
    ap.add_argument("--driver-id", help="lọc một tài xế trong CSV của Traffic-SM")
    ap.add_argument("--gateway", help="URL DF-Cloud gateway, ví dụ http://localhost:8099")
    ap.add_argument("--device-id", default="df-sim-0001")
    ap.add_argument("--models-dir", default=str(Path(__file__).resolve().parents[2] / "models"))
    ap.add_argument("--pose-method", choices=["matrix", "pnp"], default="matrix")
    ap.add_argument("--no-window", action="store_true")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=0.0)
    ap.add_argument("--fast", action="store_true", help="tệp video: xử lý nhanh nhất có thể thay vì đúng tốc độ thật")
    ap.add_argument("--events-out", help="ghi sự kiện dạng JSON Lines")
    ap.add_argument("--trace-out", help="ghi chuỗi đặc trưng để làm golden trace")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config, quick_demo_overrides() if args.quick else None)
    wall0 = datetime.now(timezone.utc)
    engine = DecisionEngine(cfg, wall_t0=wall0)
    engine.trip_id = uuid.uuid4().hex
    print(f"trip_id={engine.trip_id} device_id={args.device_id}")

    from .perception import MediaPipeSensor
    sensor = MediaPipeSensor(cfg, args.models_dir, pose_method=args.pose_method)
    try:
        src = VideoSource(args.source)
    except RuntimeError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        print("Gợi ý: kiểm tra webcam đã cắm và không bị ứng dụng khác chiếm, thử --source 1, "
              "hoặc chạy với tệp video: --source duong_dan_video.mp4", file=sys.stderr)
        sensor.close()
        return 2

    route = RouteSource.from_csv(args.route_csv, args.driver_id) if args.route_csv else None
    manual = ManualSpeed(args.speed)
    actuator = SoundActuator(enabled=not args.mute)
    uplink = None
    if args.gateway:
        from .uplink import Uplink
        uplink = Uplink(args.gateway, args.device_id, engine.trip_id, outbox=Path("out/outbox.jsonl"))
        print(f"uplink -> {args.gateway}; đã gửi bù {uplink.resend_outbox()} bản ghi từ outbox")
    for out_path in (args.events_out, args.trace_out):
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    ev_f = open(args.events_out, "a", encoding="utf-8") if args.events_out else None
    tr_f = open(args.trace_out, "w", encoding="utf-8") if args.trace_out else None

    if not args.no_window:
        import cv2
        from .osd import draw
    mute = args.mute
    # tệp video có cửa sổ: phát đúng tốc độ thật, để mốc "3 giây" trên màn hình đúng là 3 giây
    realtime = src.is_file and not args.no_window and not args.fast
    last_gps_s = -1.0
    frames = 0
    t_wall = time.monotonic()
    try:
        for t, frame in src.frames():
            obs, dbg = sensor.process(frame, t)
            motion = route.at(t) if route else manual.at(t)
            dec = engine.update(obs, motion)
            frames += 1
            if not mute:
                actuator.set_level(dec.level)
            for ev in dec.new_events:
                line = json.dumps(ev, ensure_ascii=False)
                print("EVENT", line)
                if ev_f:
                    ev_f.write(line + "\n"); ev_f.flush()
                if uplink:
                    uplink.push_event(ev)
            if uplink and motion.lat is not None and t - last_gps_s >= 1.0:
                last_gps_s = t
                uplink.push_gps(motion, wall0.timestamp() + t)
            if tr_f:
                tr_f.write(json.dumps({"obs": obs.to_dict(), "motion": motion.to_dict()}, separators=(",", ":")) + "\n")
            if args.max_seconds and t >= args.max_seconds:
                break
            if not args.no_window:
                draw(frame, obs, dec, dbg, motion.speed_kmh or 0.0, mute)
                cv2.imshow("DriveFocus", frame)
                wait_ms = max(1, int((t_wall + t - time.monotonic()) * 1000)) if realtime else 1
                key = cv2.waitKey(wait_ms) & 0xFF
                if key == ord("q"):
                    break
                if route is None:
                    if key == ord("w"):
                        manual.adjust(+10)
                    elif key == ord("s"):
                        manual.adjust(-10)
                    elif key == ord(" "):
                        manual.toggle_stop(args.speed)
                if key == ord("c"):
                    print("calibrate now:", engine.calibrate_now())
                elif key == ord("m"):
                    mute = not mute
                    actuator.set_level(0)
                elif key == ord("g"):
                    cfg.gaze._d["enabled"] = not cfg.gaze.enabled
                    print("gaze enabled:", cfg.gaze.enabled)
    except KeyboardInterrupt:
        pass
    finally:
        for ev in engine.flush():
            line = json.dumps(ev, ensure_ascii=False)
            print("EVENT", line)
            if ev_f:
                ev_f.write(line + "\n")
            if uplink:
                uplink.push_event(ev)
        elapsed = time.monotonic() - t_wall
        print(f"xong: {frames} khung trong {elapsed:.1f}s ({frames / max(elapsed, 1e-6):.1f} fps), "
              f"thống kê={engine.stats}")
        if uplink:
            uplink.close()
            print(f"uplink: đã gửi {uplink.sent}, lỗi {uplink.failed} (lỗi được ghi vào out/outbox.jsonl)")
        for f in (ev_f, tr_f):
            if f:
                f.close()
        sensor.close()
        src.close()
        actuator.close()
        if not args.no_window:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
