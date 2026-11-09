"""Bộ sinh chuỗi quan sát tổng hợp để kiểm thử thuật toán mà không cần camera."""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from drivefocus.config import load_config
from drivefocus.engine import DecisionEngine
from drivefocus.types import Decision, FrameObs, MotionObs

FPS = 15.0
EAR_OPEN = 0.30
EAR_CLOSED = 0.05


def quick_cfg(**over):
    base = {"eyes": {"calibration_s": 5.0, "perclos_window_s": 20.0},
            "head": {"neutral_min_s": 4.0, "neutral_min_speed_kmh": 20.0}}
    for k, v in over.items():
        base.setdefault(k, {}).update(v)
    return load_config(overrides=base)


def make_obs(t: float, **kw) -> FrameObs:
    d = dict(face=True, ear=EAR_OPEN, eyes_observable=True, mar=0.05, yaw=0.0, pitch=0.0, roll=0.0)
    d.update(kw)
    return FrameObs(t=t, **d)


def run(engine: DecisionEngine, seconds: float, start: float, speed: Optional[float] = 50.0,
        obs_fn: Optional[Callable[[float], dict]] = None, ctx=None) -> list[Decision]:
    """Chạy engine `seconds` giây ở 15 fps với tốc độ không đổi."""
    out: list[Decision] = []
    n = int(round(seconds * FPS))
    for i in range(n):
        t = start + i / FPS
        kw = obs_fn(t - start) if obs_fn else {}
        out.append(engine.update(make_obs(t, **kw), MotionObs(t, speed_kmh=speed), ctx))
    return out


def warm_up(engine: DecisionEngine, seconds: float = 12.0, speed: float = 50.0) -> float:
    """Chạy bình thường để qua pha vào MOVING và hiệu chỉnh. Trả về thời điểm kế tiếp."""
    run(engine, seconds, 0.0, speed)
    return seconds


def first_time(decisions: Iterable[Decision], pred) -> Optional[float]:
    for d in decisions:
        if pred(d):
            return d.t
    return None
