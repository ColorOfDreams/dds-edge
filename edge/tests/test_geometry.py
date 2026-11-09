import math

import numpy as np
import pytest

from drivefocus import geometry as g


def test_ear_open_vs_closed():
    open_eye = [(0, 0), (30, 0), (10, -5), (10, 5), (20, -5), (20, 5)]
    closed_eye = [(0, 0), (30, 0), (10, -0.5), (10, 0.5), (20, -0.5), (20, 0.5)]
    assert g.eye_aspect_ratio(open_eye) == pytest.approx(10 / 30)
    assert g.eye_aspect_ratio(closed_eye) < 0.05
    assert g.eye_aspect_ratio([(0, 0), (0, 0), (1, 1), (1, 2), (2, 1), (2, 2)]) is None


def test_ear_uses_pixels_not_normalised():
    # cùng một mắt, khung 640x480: tọa độ chuẩn hóa sẽ cho EAR sai nếu quên nhân kích thước
    px = [(100, 200), (160, 200), (115, 190), (115, 210), (145, 190), (145, 210)]
    assert g.eye_aspect_ratio(px) == pytest.approx(20 / 60)
    norm = [(x / 640, y / 480) for x, y in px]
    assert abs(g.eye_aspect_ratio(norm) - 20 / 60) > 0.05


def test_mar():
    assert g.mouth_aspect_ratio((0, 0), (0, 0), (-20, 0), (20, 0)) == pytest.approx(0.0)
    assert g.mouth_aspect_ratio((0, -15), (0, 15), (-20, 0), (20, 0)) == pytest.approx(0.75)


def _rot(axis: str, deg: float) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


@pytest.mark.parametrize("axis,deg", [("x", 20), ("x", -15), ("y", 25), ("y", -30), ("z", 10)])
def test_head_pose_recovers_known_rotation(axis, deg):
    pytest.importorskip("cv2")
    t = np.array([0.0, 0.0, 50.0])
    pts = g.project_model(_rot(axis, deg), t, 640, 480)
    yaw, pitch, roll = g.head_pose(pts, 640, 480)
    expected = {"x": pitch, "y": yaw, "z": roll}[axis]
    assert expected == pytest.approx(deg, abs=1.5)
    others = {"x": (yaw, roll), "y": (pitch, roll), "z": (yaw, pitch)}[axis]
    assert all(abs(v) < 2.0 for v in others)


def test_pitch_positive_means_looking_down():
    """Quy ước: pitch dương = cúi xuống. Hướng nhìn của mặt trong mô hình là trục -z
    (về phía camera); sau khi quay pitch dương nó phải trỏ xuống dưới (y ảnh dương)."""
    pytest.importorskip("cv2")
    R = _rot("x", 20)
    face_dir = R @ np.array([0.0, 0.0, -1.0])
    assert face_dir[1] > 0.3                      # trỏ xuống
    t = np.array([0.0, 0.0, 50.0])
    pts = g.project_model(R, t, 640, 480)
    assert g.head_pose(pts, 640, 480)[1] == pytest.approx(20, abs=1.5)
    up = g.project_model(_rot("x", -20), t, 640, 480)
    assert g.head_pose(up, 640, 480)[1] < -15     # ngẩng lên là âm


def _mp_matrix(axis, deg):
    """Ma trận kiểu MediaPipe (y lên, z về camera) cho một phép quay đã biết."""
    M = np.eye(4)
    M[:3, :3] = _rot(axis, deg)
    return M


def test_mediapipe_matrix_pose_conventions():
    # đầu cúi xuống 20 độ: hướng nhìn (+z) phải trỏ xuống (y âm); R_x(+20) cho y' = -sin(20) < 0
    yaw, pitch, roll = g.pose_from_mediapipe_matrix(_mp_matrix("x", 20))
    assert pitch == pytest.approx(20, abs=0.5) and abs(yaw) < 0.5
    # ngẩng lên thì âm
    assert g.pose_from_mediapipe_matrix(_mp_matrix("x", -20))[1] == pytest.approx(-20, abs=0.5)
    # quay đầu sang bên: |yaw| lớn, pitch ~ 0
    yaw, pitch, _ = g.pose_from_mediapipe_matrix(_mp_matrix("y", 35))
    assert abs(yaw) == pytest.approx(35, abs=0.5) and abs(pitch) < 0.5
    # ma trận có hệ số tỉ lệ vẫn đúng
    M = _mp_matrix("x", 10); M[:3, :3] *= 1.7
    assert g.pose_from_mediapipe_matrix(M)[1] == pytest.approx(10, abs=0.5)
