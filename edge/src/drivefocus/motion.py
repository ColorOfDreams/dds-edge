"""Cổng chuyển động: chỉ cho phép cảnh báo khi xe đang chạy."""
from __future__ import annotations

from typing import Optional

from .config import Cfg
from .types import MOVING, STOPPED, UNKNOWN


class MovementGate:
    """STOPPED / MOVING / UNKNOWN với hysteresis.

    - Vào MOVING: tốc độ >= enter_kmh liên tục enter_hold_s.
    - Ra MOVING: tốc độ < exit_kmh liên tục exit_hold_s.
    - Mất GPS: giữ trạng thái cũ tối đa gps_loss_hold_s, sau đó dùng IMU;
      nếu không có IMU thì UNKNOWN.
    """

    def __init__(self, cfg: Cfg):
        self.c = cfg.moving
        self.state = STOPPED
        self._enter_since: Optional[float] = None
        self._exit_since: Optional[float] = None
        self._last_fix_t: Optional[float] = None

    def update(self, t: float, speed_kmh: Optional[float], vibration: Optional[float] = None) -> str:
        c = self.c
        if speed_kmh is None:
            lost = float("inf") if self._last_fix_t is None else t - self._last_fix_t
            if lost <= c.gps_loss_hold_s:
                return self.state
            if vibration is not None:
                self.state = MOVING if vibration >= c.imu_vibration_thresh else STOPPED
            else:
                self.state = UNKNOWN
            self._enter_since = self._exit_since = None
            return self.state

        self._last_fix_t = t
        if self.state == UNKNOWN:
            self.state = STOPPED
        if self.state != MOVING:
            self._exit_since = None
            if speed_kmh >= c.enter_kmh:
                if self._enter_since is None:
                    self._enter_since = t
                if t - self._enter_since >= c.enter_hold_s:
                    self.state = MOVING
                    self._enter_since = None
            else:
                self._enter_since = None
        else:
            self._enter_since = None
            if speed_kmh < c.exit_kmh:
                if self._exit_since is None:
                    self._exit_since = t
                if t - self._exit_since >= c.exit_hold_s:
                    self.state = STOPPED
                    self._exit_since = None
            else:
                self._exit_since = None
        return self.state
