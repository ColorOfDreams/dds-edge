"""Phát lại chuỗi đặc trưng đã ghi (golden trace) qua DecisionEngine.

Cùng chuỗi vào thì cho cùng chuỗi sự kiện. Đây là cách bảo đảm bản port sang K230 không đổi
hành vi: ghi trace từ giả lập, rồi chạy lại trên thiết bị và so sánh sự kiện.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from .config import Cfg, load_config
from .engine import DecisionEngine
from .types import Context, FrameObs, MotionObs

FIXED_WALL_T0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def write_trace(path: str | Path, frames: Iterable[tuple[FrameObs, MotionObs]]) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for obs, motion in frames:
            f.write(json.dumps({"obs": obs.to_dict(), "motion": motion.to_dict()}, separators=(",", ":")) + "\n")
            n += 1
    return n


def read_trace(path: str | Path) -> Iterator[tuple[FrameObs, MotionObs]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                yield FrameObs.from_dict(d["obs"]), MotionObs.from_dict(d["motion"])


def run_trace(frames: Iterable[tuple[FrameObs, MotionObs]], cfg: Optional[Cfg] = None,
              wall_t0: datetime = FIXED_WALL_T0, ctx: Optional[Context] = None) -> dict[str, Any]:
    engine = DecisionEngine(cfg or load_config(), wall_t0=wall_t0)
    engine.trip_id = "replay"
    events: list[dict[str, Any]] = []
    max_level = 0
    n = 0
    for obs, motion in frames:
        dec = engine.update(obs, motion, ctx)
        events.extend(dec.new_events)
        max_level = max(max_level, dec.level)
        n += 1
    events.extend(engine.flush())
    return {"frames": n, "max_level": max_level, "events": events, "stats": engine.stats}


def canonical_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chỉ giữ các trường xác định (bỏ event_id ngẫu nhiên) để so sánh golden."""
    keep = ("type", "level", "ts_start", "ts_end", "duration_ms", "distance_m", "speed_kmh_avg", "speed_kmh_max")
    return [{k: e[k] for k in keep} for e in events]


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Phát lại trace đặc trưng qua thuật toán DriveFocus")
    ap.add_argument("trace")
    ap.add_argument("--config")
    ap.add_argument("--quick", action="store_true", help="rút ngắn hiệu chỉnh")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = ap.parse_args(argv)
    from .config import quick_demo_overrides
    cfg = load_config(args.config, quick_demo_overrides() if args.quick else None)
    result = run_trace(read_trace(args.trace), cfg)
    print(json.dumps({"frames": result["frames"], "max_level": result["max_level"],
                      "events": canonical_events(result["events"]), "stats": result["stats"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
