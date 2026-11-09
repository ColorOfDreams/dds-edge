"""Kiểu dữ liệu đi qua ranh giới giữa cảm biến và thuật toán quyết định.

Tầng quyết định chỉ nhận `FrameObs` và `MotionObs`, nên chạy được với số liệu
từ MediaPipe, từ SDK K230 hoặc từ tệp ghi sẵn (golden trace).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

MOVING = "MOVING"
STOPPED = "STOPPED"
UNKNOWN = "UNKNOWN"


@dataclass
class FrameObs:
    """Số đo từ một khung hình. `None` nghĩa là KHÔNG BIẾT."""

    t: float
    face: bool = False
    ear: Optional[float] = None          # Eye Aspect Ratio (trung bình hai mắt)
    eyes_observable: bool = False        # mắt có đủ sáng/rõ để tin EAR không
    mar: Optional[float] = None          # Mouth Aspect Ratio
    yaw: Optional[float] = None          # độ
    pitch: Optional[float] = None        # độ, dương = cúi xuống
    roll: Optional[float] = None
    gaze: Optional[float] = None         # độ lệch mống mắt / chiều rộng mắt
    hand_ear: Optional[float] = None     # khoảng cách tay-tai gần nhất / chiều rộng mặt
    hand_mouth: Optional[float] = None
    hand_eye: Optional[float] = None
    hands_visible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FrameObs":
        return FrameObs(**d)


@dataclass
class MotionObs:
    """Số đo chuyển động. `speed_kmh = None` nghĩa là không có GPS."""

    t: float
    speed_kmh: Optional[float] = None
    vibration: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MotionObs":
        return MotionObs(**d)


@dataclass
class Context:
    """Ngữ cảnh đường từ Traffic-SM (không bắt buộc, có thời hạn)."""

    speed_limit_kmh: Optional[float] = None
    congestion: Optional[str] = None     # FREE | SLOW | CONGESTED
    expires_at: Optional[float] = None   # cùng đồng hồ với `t`


@dataclass
class Decision:
    t: float
    level: int                            # mức đang hiển thị (đã qua FSM)
    raw_level: int                        # mức thô theo điều kiện
    levels: dict[str, int] = field(default_factory=dict)
    moving_state: str = STOPPED
    ear: Optional[float] = None
    ear_norm: Optional[float] = None
    closure_run: float = 0.0
    perclos: float = 0.0
    perclos_ready: bool = False
    budget: float = 1.0
    dyaw: Optional[float] = None
    dpitch: Optional[float] = None
    head_calibrated: bool = False
    eye_calibrated: bool = False
    yawns_10min: int = 0
    new_events: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
