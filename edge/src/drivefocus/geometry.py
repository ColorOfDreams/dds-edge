"""Hình học thuần: EAR, MAR, tư thế đầu từ PnP. Không phụ thuộc MediaPipe."""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np


def _dist(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


def eye_aspect_ratio(pts: Sequence[Sequence[float]]) -> Optional[float]:
    """EAR của một mắt từ 6 điểm theo thứ tự [khóe1, khóe2, trên1, dưới1, trên2, dưới2].

    Thứ tự này khớp chỉ số MediaPipe dùng ở e-candeloro/driver-state-detection:
    [33, 133, 160, 144, 158, 153] và [362, 263, 385, 380, 387, 373].
    Tọa độ phải là PIXEL (tọa độ chuẩn hóa làm méo tỉ lệ khung hình).
    Trả None nếu mắt bị co về bề rộng ~0.
    """
    width = _dist(pts[0], pts[1])
    if width <= 1e-6:
        return None
    return (_dist(pts[2], pts[3]) + _dist(pts[4], pts[5])) / (2.0 * width)


def mean_ear(left: Optional[float], right: Optional[float]) -> Optional[float]:
    values = [v for v in (left, right) if v is not None]
    return float(np.mean(values)) if values else None


def mouth_aspect_ratio(upper_inner, lower_inner, corner_left, corner_right) -> Optional[float]:
    """MAR = độ mở môi trong / chiều rộng miệng."""
    width = _dist(corner_left, corner_right)
    if width <= 1e-6:
        return None
    return _dist(upper_inner, lower_inner) / width


# Mô hình 3D mặt lấy từ canonical_face_model.obj của MediaPipe (Apache-2.0), đơn vị cm,
# đã đổi sang hệ tọa độ OpenCV camera: x sang phải, y xuống, z ra xa camera
# (gốc canonical: y lên, z về phía camera, nên đảo dấu y và z). Mặt nhìn thẳng vào camera
# thì ma trận quay xấp xỉ đơn vị.
# Thứ tự: mũi (1), cằm (152), khóe mắt ngoài bên TRÁI ẢNH (33) và PHẢI ẢNH (263),
# khóe miệng bên TRÁI ẢNH (61) và PHẢI ẢNH (291).
MODEL_POINTS_3D = np.array(
    [
        (0.0, 1.126865, -7.475604),
        (0.0, 9.403378, -4.264492),
        (-4.445859, -2.663991, -3.173422),
        (4.445859, -2.663991, -3.173422),
        (-2.456206, 4.342621, -4.283884),
        (2.456206, 4.342621, -4.283884),
    ],
    dtype=np.float64,
)


def rotation_to_euler(R: np.ndarray) -> tuple[float, float, float]:
    """Trả (yaw, pitch, roll) bằng độ. pitch dương = cúi xuống (mũi đi xuống ảnh)."""
    pitch = math.atan2(R[2, 1], R[2, 2])
    yaw = math.atan2(-R[2, 0], math.hypot(R[2, 1], R[2, 2]))
    roll = math.atan2(R[1, 0], R[0, 0])
    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def pose_from_mediapipe_matrix(M: np.ndarray) -> Optional[tuple[float, float, float]]:
    """(yaw, pitch, roll) độ từ ma trận biến đổi mặt 4x4 của MediaPipe Face Landmarker.

    Ma trận khớp mô hình mặt chuẩn (468 điểm) vào ảnh, ổn định hơn PnP 6 điểm. Hệ chuẩn của
    MediaPipe: x sang phải, y lên, z về phía camera; hướng nhìn của mặt là +z. pitch dương =
    cúi xuống = vectơ hướng nhìn trỏ xuống (y âm).
    """
    M = np.asarray(M, dtype=float)
    if M.shape != (4, 4):
        return None
    R = M[:3, :3]
    det = np.linalg.det(R)
    if det <= 0:
        return None
    R = R / np.cbrt(det)                  # bỏ hệ số tỉ lệ nếu có
    fwd = R @ np.array([0.0, 0.0, 1.0])
    pitch = math.degrees(-math.asin(max(-1.0, min(1.0, float(fwd[1])))))
    yaw = math.degrees(math.atan2(fwd[0], fwd[2]))
    roll = math.degrees(math.atan2(R[1, 0], R[0, 0]))
    return yaw, pitch, roll


def head_pose(image_points: np.ndarray, frame_w: int, frame_h: int) -> Optional[tuple[float, float, float]]:
    """Tư thế đầu từ 6 điểm ảnh (pixel) tương ứng MODEL_POINTS_3D bằng PnP."""
    import cv2  # import muộn để phần thuật toán không bắt buộc có OpenCV

    focal = float(frame_w)
    camera = np.array([[focal, 0, frame_w / 2.0], [0, focal, frame_h / 2.0], [0, 0, 1]], dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(
        MODEL_POINTS_3D,
        np.asarray(image_points, dtype=np.float64),
        camera,
        np.zeros((4, 1)),
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    if tvec[2, 0] < 0:  # mặt phải nằm trước camera
        return None
    return rotation_to_euler(R)


def project_model(R: np.ndarray, t: np.ndarray, frame_w: int, frame_h: int) -> np.ndarray:
    """Chiếu mô hình 3D lên ảnh; dùng để kiểm thử (tạo điểm ảnh biết trước góc)."""
    focal = float(frame_w)
    cam = MODEL_POINTS_3D @ R.T + t
    xs = focal * cam[:, 0] / cam[:, 2] + frame_w / 2.0
    ys = focal * cam[:, 1] / cam[:, 2] + frame_h / 2.0
    return np.stack([xs, ys], axis=1)
