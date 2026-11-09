"""Bộ máy quyết định: gộp các bộ đo thành mức cảnh báo 0..4 và sự kiện.

Hàm thuần của chuỗi (FrameObs, MotionObs). Cùng chuỗi đầu vào thì cho cùng chuỗi
sự kiện, nên kiểm thử và so sánh PC với K230 bằng golden trace.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import Cfg
from .estimators import AttentionBudget, EyeEstimator, HandEstimator, HeadEstimator, YawnEstimator
from .motion import MovementGate
from .types import Context, Decision, FrameObs, MotionObs, MOVING, STOPPED, UNKNOWN

EVENT_TYPES = ("EYES_CLOSED", "PERCLOS_HIGH", "YAWN", "HEAD_NOD", "LOOK_AWAY", "PHONE", "BEHAVIOR_OTHER", "NO_FACE")
CAUSE_TO_TYPE = {"look_away": "LOOK_AWAY", "phone": "PHONE", "mouth": "BEHAVIOR_OTHER"}


class _Segment:
    def __init__(self, type_: str, t: float, level: int, speed: float, lat, lng, dist0: float, observable: bool):
        self.type, self.t0, self.t1 = type_, t, t
        self.level = level
        self.speeds = [speed]
        self.lat, self.lng = lat, lng
        self.dist0 = dist0
        self.observable = observable
        self.low_since: Optional[float] = None
        self.dist1 = dist0


class SegmentTracker:
    """Gom mức theo từng loại thành đoạn liên tục; đóng đoạn khi mức về 0 đủ lâu."""

    def __init__(self, end_hold_s: float):
        self.end_hold = end_hold_s
        self.open: dict[str, _Segment] = {}

    def update(self, t: float, levels: dict[str, int], speed: float, lat, lng, dist: float,
               observable: bool) -> list[_Segment]:
        done: list[_Segment] = []
        for type_ in EVENT_TYPES:
            lvl = levels.get(type_, 0)
            seg = self.open.get(type_)
            if lvl > 0:
                if seg is None:
                    seg = self.open[type_] = _Segment(type_, t, lvl, speed, lat, lng, dist, observable)
                seg.t1 = t
                seg.level = max(seg.level, lvl)
                seg.speeds.append(speed)
                seg.low_since = None
                seg.dist1 = dist
            elif seg is not None:
                if seg.low_since is None:
                    seg.low_since = t
                if t - seg.low_since >= self.end_hold:
                    done.append(self.open.pop(type_))
        return done

    def flush(self) -> list[_Segment]:
        done = list(self.open.values())
        self.open.clear()
        return done


class DecisionEngine:
    def __init__(self, cfg: Cfg, wall_t0: Optional[datetime] = None, fw_version: str = "sim-0.1"):
        self.cfg = cfg
        self.gate = MovementGate(cfg)
        self.eyes = EyeEstimator(cfg)
        self.yawn = YawnEstimator(cfg)
        self.head = HeadEstimator(cfg)
        self.hands = HandEstimator(cfg)
        self.budget = AttentionBudget(cfg)
        self.tracker = SegmentTracker(cfg.fsm.event_end_hold_s)
        self.wall_t0 = wall_t0 or datetime.now(timezone.utc)
        self.fw_version = fw_version
        self.trip_id: Optional[str] = None
        self.shown = 0
        self._lower_since: Optional[float] = None
        self._last_t: Optional[float] = None
        self._no_face_run = 0.0
        self._dist_m = 0.0
        self._last_motion = MotionObs(0.0)
        self._ctx_used: Optional[dict[str, Any]] = None
        self._last_cause = "LOOK_AWAY"
        self.stats = {"events": {}, "moving_s": 0.0, "distance_m": 0.0, "yawns": 0}

    # ------------------------------------------------------------------ tiện ích
    def _speed_factor(self, v: Optional[float]) -> float:
        s = self.cfg.speed_scaling
        if not s.enabled or v is None or v <= 0:
            return 1.0
        return min(1.0, max(s.min_factor, s.v_ref_kmh / v))

    @staticmethod
    def _count(value: float, thresholds) -> int:
        return sum(1 for th in thresholds if value >= th)

    def _iso(self, t: float) -> str:
        return (self.wall_t0 + timedelta(seconds=t)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def calibrate_now(self) -> dict[str, bool]:
        return {"eyes": self.eyes.calibrate_now(), "head": self.head.calibrate_now()}

    # ---------------------------------------------------------------- cập nhật
    def update(self, obs: FrameObs, motion: Optional[MotionObs] = None, ctx: Optional[Context] = None) -> Decision:
        t = obs.t
        motion = motion or MotionObs(t)
        dt = 0.0 if self._last_t is None else max(0.0, t - self._last_t)
        self._last_t = t
        speed = motion.speed_kmh
        state = self.gate.update(t, speed, motion.vibration)
        moving = state == MOVING
        if speed is not None and moving:
            self._dist_m += speed / 3.6 * dt
            self.stats["moving_s"] += dt
            self.stats["distance_m"] = round(self._dist_m, 1)
        if motion.lat is not None:
            self._last_motion = motion

        eye = self.eyes.update(t, obs.face, obs.ear, obs.eyes_observable, allow_calib=moving)
        head = self.head.update(t, obs.yaw if obs.face else None, obs.pitch if obs.face else None, obs.gaze,
                                speed if moving else None)
        if self.yawn.update(t, obs.face, obs.mar):
            self.stats["yawns"] += 1
        hands = self.hands.update(t, obs.face, obs.hand_ear, obs.hand_mouth, obs.hand_eye, obs.hands_visible)

        if not moving:
            if state == STOPPED:
                self.eyes.reset_run()
                self.budget.reset()
            self._no_face_run = 0.0
        elif not obs.face:
            self._no_face_run += dt
        else:
            self._no_face_run = 0.0

        factor = self._speed_factor(speed)
        levels: dict[str, int] = {k: 0 for k in EVENT_TYPES}
        flags: list[str] = []
        if not obs.face:
            flags.append("NO_FACE")
        elif not obs.eyes_observable:
            flags.append("EYES_UNOBSERVABLE")
        if not eye.calibrated:
            flags.append("EYE_UNCALIBRATED")
        if not head.calibrated:
            flags.append("HEAD_UNCALIBRATED")

        a = self.budget.a
        if moving or state == UNKNOWN:
            run = eye.closure_run
            closed_th = [x * factor for x in self.cfg.eyes.closed_s]
            lvl_closed = self._count(run, closed_th)
            slump_l4 = bool(head.slump and run >= 1.5 * factor)
            if state == UNKNOWN:
                # Chính sách an toàn khi không biết xe có chạy không: chỉ giữ mức 4
                lvl_closed = 4 if lvl_closed >= 4 else 0
                levels["EYES_CLOSED"] = lvl_closed
                if slump_l4:
                    levels["HEAD_NOD"] = 4
            else:
                levels["EYES_CLOSED"] = lvl_closed
                if eye.perclos_ready:
                    levels["PERCLOS_HIGH"] = self._count(eye.perclos, self.cfg.eyes.perclos)
                levels["YAWN"] = self.yawn.level(t)
                if head.nod and run >= 0.5 * factor:
                    levels["HEAD_NOD"] = 3
                if slump_l4:
                    levels["HEAD_NOD"] = 4
                active = {
                    "look_away": bool(head.off_road),
                    "phone": hands["phone"],
                    "mouth": hands["mouth"],
                }
                # Mất mặt không đưa vào ngân sách; xử lý riêng ở NO_FACE
                if not obs.face:
                    active = {k: False for k in active}
                a, lvl_b, dom = self.budget.update(t, active, rate_div=factor)
                if dom is not None and lvl_b > 0:
                    levels[CAUSE_TO_TYPE[dom]] = lvl_b
                elif lvl_b > 0:
                    # đang hồi phục nhưng ngân sách chưa đầy: giữ loại cuối cùng gây ra
                    levels[self._last_cause] = lvl_b
                if dom is not None:
                    self._last_cause = CAUSE_TO_TYPE[dom]
                nf2, nf3 = self.cfg.no_face_s
                levels["NO_FACE"] = 3 if self._no_face_run >= nf3 else (2 if self._no_face_run >= nf2 else 0)
        raw = max(levels.values())

        # Ngữ cảnh đường (nếu còn hiệu lực): vượt tốc độ cho phép thì tăng một mức, tối đa 3
        self._ctx_used = None
        if ctx is not None and (ctx.expires_at is None or t <= ctx.expires_at) and moving:
            if (ctx.speed_limit_kmh is not None and speed is not None
                    and speed > ctx.speed_limit_kmh + self.cfg.context.overspeed_margin_kmh and 1 <= raw < 3):
                raw += 1
                self._ctx_used = {"speed_limit_kmh": ctx.speed_limit_kmh, "congestion": ctx.congestion,
                                  "adjust": "overspeed+1"}

        # FSM hiển thị: lên ngay, xuống chậm
        if raw >= self.shown:
            self.shown = raw
            self._lower_since = None
        else:
            if self._lower_since is None:
                self._lower_since = t
            hold = self.cfg.fsm.down_hold_s[self.shown - 1]
            if t - self._lower_since >= hold:
                self.shown -= 1
                self._lower_since = t
        if state == STOPPED:
            self.shown = 0
            self._lower_since = None

        events = self._collect_events(t, levels, speed or 0.0, obs.eyes_observable)
        return Decision(
            t=t, level=self.shown, raw_level=raw, levels=levels, moving_state=state,
            ear=obs.ear, ear_norm=eye.ear_norm, closure_run=eye.closure_run, perclos=eye.perclos,
            perclos_ready=eye.perclos_ready, budget=a, dyaw=head.dyaw, dpitch=head.dpitch,
            head_calibrated=head.calibrated, eye_calibrated=eye.calibrated,
            yawns_10min=self.yawn.count(t), new_events=events, flags=flags,
        )

    # ------------------------------------------------------------------ sự kiện
    def _segment_to_event(self, seg: _Segment) -> dict[str, Any]:
        dist1 = seg.dist1
        ev = {
            "schema": "df.event.v1",
            "event_id": uuid.uuid4().hex,
            "trip_id": self.trip_id,
            "type": seg.type,
            "level": seg.level,
            "ts_start": self._iso(seg.t0),
            "ts_end": self._iso(seg.t1),
            "duration_ms": int(round((seg.t1 - seg.t0) * 1000)),
            "distance_m": round(max(0.0, dist1 - seg.dist0), 1),
            "speed_kmh_avg": round(sum(seg.speeds) / len(seg.speeds), 1),
            "speed_kmh_max": round(max(seg.speeds), 1),
            "lat": seg.lat, "lng": seg.lng,
            "eyes_observable": seg.observable,
            "fw_version": self.fw_version,
            "config_version": self.cfg.config_version,
        }
        if self._ctx_used:
            ev["context_used"] = self._ctx_used
        self.stats["events"][seg.type] = self.stats["events"].get(seg.type, 0) + 1
        return ev

    def _collect_events(self, t: float, levels: dict[str, int], speed: float, observable: bool) -> list[dict[str, Any]]:
        segs = self.tracker.update(t, levels, speed, self._last_motion.lat, self._last_motion.lng,
                                   self._dist_m, observable)
        return [self._segment_to_event(s) for s in segs]

    def flush(self) -> list[dict[str, Any]]:
        """Đóng các đoạn còn mở khi kết thúc phiên."""
        return [self._segment_to_event(s) for s in self.tracker.flush()]
