"""Các bộ đo: nhắm mắt/PERCLOS, ngáp, tư thế đầu, bàn tay, ngân sách chú ý.

Mỗi bộ đo nhận quan sát có thể là KHÔNG BIẾT (None). Quy tắc chung (học từ
e-candeloro/driver-state-detection): KHÔNG BIẾT không cộng và không làm suy giảm
bộ đếm, và bị loại khỏi mẫu số của PERCLOS.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median
from typing import Deque, Optional

from .config import Cfg


# --------------------------------------------------------------------------- mắt
@dataclass
class EyeState:
    closed: Optional[bool]
    ear_norm: Optional[float]
    closure_run: float
    perclos: float
    perclos_ready: bool
    calibrated: bool


class EyeEstimator:
    def __init__(self, cfg: Cfg):
        self.c = cfg.eyes
        self.o = cfg.observation
        self.baseline: Optional[float] = None
        self._calib: list[tuple[float, float]] = []   # (t, ear) khi xe chạy, mắt quan sát tốt
        self._calib_valid_s = 0.0
        self._last_valid_t: Optional[float] = None
        self._recent: Deque[tuple[float, float]] = deque()  # 10 s gần nhất, cho calibrate_now
        self._run_start: Optional[float] = None
        self._gap_start: Optional[float] = None
        self._unknown_start: Optional[float] = None
        self._samples: Deque[tuple[float, Optional[bool]]] = deque()
        self._ready = False
        self.run = 0.0

    # -- hiệu chỉnh
    def _threshold(self) -> float:
        if self.baseline is not None:
            return self.c.ear_closed_ratio * self.baseline
        return self.c.ear_closed_abs_fallback

    def _try_finish_calibration(self) -> None:
        if self.baseline is None and self._calib_valid_s >= self.c.calibration_s and self._calib:
            base = median(e for _, e in self._calib)
            lo, hi = self.c.baseline_range
            if lo <= base <= hi:
                self.baseline = float(base)
            else:  # số đo vô lý: giữ ngưỡng tuyệt đối, thử lại với dữ liệu mới
                self._calib.clear()
                self._calib_valid_s = 0.0

    def calibrate_now(self, window_s: float = 5.0) -> bool:
        """Hiệu chỉnh ngay từ `window_s` giây gần nhất (phím tắt khi demo)."""
        if not self._recent:
            return False
        t_end = self._recent[-1][0]
        vals = [e for t, e in self._recent if t >= t_end - window_s]
        if len(vals) < 5:
            return False
        base = float(median(vals))
        lo, hi = self.c.baseline_range
        if not lo <= base <= hi:
            return False
        self.baseline = base
        return True

    def reset_run(self) -> None:
        self._run_start = None
        self._gap_start = None
        self.run = 0.0

    # -- cập nhật theo khung
    def update(self, t: float, face: bool, ear: Optional[float], observable: bool, allow_calib: bool) -> EyeState:
        known = bool(face and observable and ear is not None)
        closed: Optional[bool] = None
        ear_norm: Optional[float] = None
        if known:
            assert ear is not None
            closed = ear < self._threshold()
            ear_norm = ear / self.baseline if self.baseline else None
            self._recent.append((t, ear))
            while self._recent and self._recent[0][0] < t - 10.0:
                self._recent.popleft()
            if allow_calib and self.baseline is None:
                self._calib.append((t, ear))
                if self._last_valid_t is not None:
                    self._calib_valid_s += min(0.5, t - self._last_valid_t)
                self._try_finish_calibration()
            self._last_valid_t = t
        else:
            self._last_valid_t = None

        self._update_run(t, closed)
        self._update_perclos(t, closed)
        return EyeState(closed, ear_norm, self.run, self._perclos, self._ready, self.baseline is not None)

    def _update_run(self, t: float, closed: Optional[bool]) -> None:
        tol = self.c.closure_gap_tolerance_s
        if closed is None:
            if self._unknown_start is None:
                self._unknown_start = t
            if t - self._unknown_start > self.o.unknown_reset_s:
                self.reset_run()
            return  # KHÔNG BIẾT: giữ nguyên bộ đếm trong khoảng ngắn
        self._unknown_start = None
        if closed:
            if self._run_start is None:
                self._run_start = t
            self._gap_start = None
            self.run = t - self._run_start
        else:
            if self._run_start is None:
                self.run = 0.0
                return
            if self._gap_start is None:
                self._gap_start = t
            if t - self._gap_start > tol:
                self.reset_run()
            else:
                self.run = t - self._run_start  # lỗ hổng ngắn: coi như vẫn đang nhắm

    # -- PERCLOS trượt theo thời gian
    _perclos = 0.0

    def _update_perclos(self, t: float, closed: Optional[bool]) -> None:
        win = self.c.perclos_window_s
        self._samples.append((t, closed))
        start = t - win
        while len(self._samples) > 1 and self._samples[1][0] <= start:
            self._samples.popleft()
        closed_d = valid_d = 0.0
        samples = list(self._samples)
        for (t0, s0), (t1, _) in zip(samples, samples[1:]):
            dur = max(0.0, t1 - max(t0, start))
            if s0 is not None:
                valid_d += dur
                if s0:
                    closed_d += dur
        self._perclos = closed_d / valid_d if valid_d else 0.0
        full = bool(samples) and samples[0][0] <= start
        self._ready = full and valid_d >= win * self.c.perclos_min_valid_fraction


# -------------------------------------------------------------------------- ngáp
class YawnEstimator:
    def __init__(self, cfg: Cfg):
        self.c = cfg.mouth
        self._since: Optional[float] = None
        self._counted = False
        self._times: Deque[float] = deque()
        self.active_until = -1.0

    def update(self, t: float, face: bool, mar: Optional[float]) -> bool:
        """Trả True ở khung phát hiện một cái ngáp mới."""
        new = False
        if face and mar is not None and mar > self.c.mar_yawn:
            if self._since is None:
                self._since = t
            if not self._counted and t - self._since >= self.c.yawn_min_s:
                self._counted = True
                self._times.append(t)
                self.active_until = t + self.c.yawn_event_s
                new = True
        elif mar is not None or not face:
            self._since = None
            self._counted = False
        while self._times and self._times[0] < t - self.c.yawn_window_s:
            self._times.popleft()
        return new

    def count(self, t: float) -> int:
        while self._times and self._times[0] < t - self.c.yawn_window_s:
            self._times.popleft()
        return len(self._times)

    def level(self, t: float) -> int:
        if t > self.active_until:
            return 0
        n = self.count(t)
        return sum(1 for th in self.c.yawn_count if n >= th)


# ----------------------------------------------------------------------- tư thế
@dataclass
class HeadState:
    dyaw: Optional[float]
    dpitch: Optional[float]      # dương = cúi xuống so với trung tính
    off_road: Optional[bool]
    nod: bool
    slump: bool
    calibrated: bool


class HeadEstimator:
    def __init__(self, cfg: Cfg):
        self.c = cfg.head
        self.g = cfg.gaze
        self.neutral: Optional[tuple[float, float]] = None
        self._samples: Deque[tuple[float, float, float]] = deque()  # (t, yaw, pitch) khi hiệu chỉnh được
        self._valid_s = 0.0
        self._last_t: Optional[float] = None
        self._recent: Deque[tuple[float, float, float]] = deque()
        self._pitch_hist: Deque[tuple[float, float]] = deque()
        self._nod_t = -1e9
        self._since_refresh = 0

    def calibrate_now(self, window_s: float = 3.0) -> bool:
        if len(self._recent) < 5:
            return False
        t_end = self._recent[-1][0]
        pts = [(y, p) for t, y, p in self._recent if t >= t_end - window_s]
        if len(pts) < 5:
            return False
        self.neutral = (median(y for y, _ in pts), median(p for _, p in pts))
        return True

    def update(self, t: float, yaw: Optional[float], pitch: Optional[float], gaze: Optional[float],
               speed_kmh: Optional[float]) -> HeadState:
        if yaw is None or pitch is None:
            self._last_t = None
            return HeadState(None, None, None, False, False, self.neutral is not None)

        self._recent.append((t, yaw, pitch))
        while self._recent and self._recent[0][0] < t - 10.0:
            self._recent.popleft()

        if speed_kmh is not None and speed_kmh >= self.c.neutral_min_speed_kmh:
            self._samples.append((t, yaw, pitch))
            if self._last_t is not None:
                self._valid_s += min(0.5, t - self._last_t)
            while self._samples and self._samples[0][0] < t - self.c.neutral_memory_s:
                self._samples.popleft()
            self._since_refresh += 1
            if self._valid_s >= self.c.neutral_min_s and self.neutral is None:
                self.neutral = (median(s[1] for s in self._samples), median(s[2] for s in self._samples))
                self._since_refresh = 0
            elif self.neutral is not None and self._since_refresh >= 30:
                # cập nhật chậm theo trí nhớ ngắn (cửa sổ neutral_memory_s), 30 mẫu một lần
                self.neutral = (median(s[1] for s in self._samples), median(s[2] for s in self._samples))
                self._since_refresh = 0
        self._last_t = t

        y0, p0 = self.neutral if self.neutral else (0.0, 0.0)
        dyaw, dpitch = yaw - y0, pitch - p0
        factor = 1.0 if self.neutral else self.c.uncalibrated_factor
        off = abs(dyaw) > self.c.yaw_deg * factor or dpitch > self.c.pitch_down_deg * factor
        if self.g.enabled and gaze is not None and gaze > self.g.score_thresh:
            off = True

        self._pitch_hist.append((t, dpitch))
        while self._pitch_hist and self._pitch_hist[0][0] < t - self.c.nod_window_s:
            self._pitch_hist.popleft()
        lowest = min(p for _, p in self._pitch_hist)
        if dpitch - lowest >= self.c.nod_delta_deg:
            self._nod_t = t
        nod = (t - self._nod_t) <= self.c.nod_hold_s
        slump = dpitch >= self.c.slump_pitch_deg
        return HeadState(dyaw, dpitch, off, nod, slump, self.neutral is not None)


# ---------------------------------------------------------------------- bàn tay
class LeakyTimer:
    """Cộng khi điều kiện đúng, suy giảm theo hàm mũ khi sai. None thì giữ nguyên."""

    def __init__(self, decay_per_s: float):
        self.decay = decay_per_s
        self.value = 0.0
        self._last: Optional[float] = None

    def update(self, t: float, cond: Optional[bool]) -> float:
        dt = 0.0 if self._last is None else max(0.0, t - self._last)
        self._last = t
        if cond is None:
            return self.value
        self.value = self.value + dt if cond else self.value * (self.decay ** dt)
        return self.value


class HandEstimator:
    """Luật hình học tay–mặt (học từ demo dms_system của SDK K230, chuẩn hóa theo chiều rộng mặt)."""

    def __init__(self, cfg: Cfg):
        self.c = cfg.hands
        self._ear = LeakyTimer(self.c.decay_per_s)
        self._mouth = LeakyTimer(self.c.decay_per_s)

    def update(self, t: float, face: bool, hand_ear: Optional[float], hand_mouth: Optional[float],
               hand_eye: Optional[float], hands_visible: bool) -> dict[str, bool]:
        if not face:
            return {"phone": False, "mouth": False}
        c = self.c
        # tay đang chạm vùng mắt (dụi mắt) thì loại, vì dễ nhầm với gọi điện/uống nước
        eye_rub = hand_eye is not None and (
            (hand_ear is None or hand_eye < hand_ear) and (hand_mouth is None or hand_eye < hand_mouth)
        ) and hand_eye < c.near_ear_k
        near_ear: Optional[bool] = None if not hands_visible else (
            hand_ear is not None and hand_ear < c.near_ear_k and not eye_rub)
        near_mouth: Optional[bool] = None if not hands_visible else (
            hand_mouth is not None and hand_mouth < c.near_mouth_k and not eye_rub)
        if hands_visible and near_ear and near_mouth:  # chọn cái gần hơn
            if (hand_ear or 9) <= (hand_mouth or 9):
                near_mouth = False
            else:
                near_ear = False
        # không thấy tay trong khung => coi là không có tay (False), không phải KHÔNG BIẾT
        ne = False if near_ear is None else near_ear
        nm = False if near_mouth is None else near_mouth
        return {
            "phone": self._ear.update(t, ne) >= c.min_s,
            "mouth": self._mouth.update(t, nm) >= c.min_s,
        }


# ------------------------------------------------------------ ngân sách chú ý
class AttentionBudget:
    """Ý tưởng `awareness` của openpilot: giảm đều khi mất tập trung, hồi nhanh hơn khi đang thấp."""

    def __init__(self, cfg: Cfg):
        self.c = cfg.attention_budget
        self.a = 1.0
        self._last: Optional[float] = None

    def reset(self) -> None:
        self.a = 1.0
        self._last = None

    def update(self, t: float, active: dict[str, bool], rate_div: float = 1.0) -> tuple[float, int, Optional[str]]:
        dt = 0.0 if self._last is None else max(0.0, t - self._last)
        self._last = t
        causes = [k for k, v in active.items() if v]
        dominant: Optional[str] = None
        if causes:
            dominant = max(causes, key=lambda k: self.c.weights[k])
            w = self.c.weights[dominant]
            self.a -= w * dt / (self.c.t_empty_s * rate_div)
        else:
            fmin, fmax = self.c.recovery_factor
            f = fmin + (fmax - fmin) * (1.0 - self.a)
            self.a += f * dt / self.c.t_empty_s
        self.a = min(1.0, max(0.0, self.a))
        return self.a, self.level(), dominant

    def level(self) -> int:
        if self.a <= 0.0:
            return 4
        return sum(1 for th in self.c.levels if self.a < th)
