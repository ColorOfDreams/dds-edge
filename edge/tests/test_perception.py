"""Kiểm thử tầng cảm biến trên ảnh thật. Bỏ qua nếu thiếu mô hình/ảnh mẫu (không commit)."""
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
pytest.importorskip("mediapipe")

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
SAMPLE = MODELS / "samples" / "portrait.jpg"
pytestmark = pytest.mark.skipif(
    not (MODELS / "face_landmarker.task").exists() or not SAMPLE.exists(),
    reason="cần models/face_landmarker.task, hand_landmarker.task và models/samples/portrait.jpg",
)


@pytest.fixture(scope="module")
def sensor():
    from drivefocus.config import load_config
    from drivefocus.perception import MediaPipeSensor
    s = MediaPipeSensor(load_config(), MODELS)
    yield s
    s.close()


def _obs(sensor, img, t0):
    for i in range(3):
        o, d = sensor.process(img, t0 + 0.1 * i)
    return o, d


def test_open_eyes_ear_in_plausible_range(sensor):
    img = cv2.imread(str(SAMPLE))
    o, _ = _obs(sensor, img, 0.0)
    assert o.face and o.eyes_observable
    assert 0.15 < o.ear < 0.45
    assert abs(o.yaw) < 15 and abs(o.pitch) < 15       # ảnh gần như nhìn thẳng (ma trận MediaPipe)
    assert o.mar is not None and o.mar >= 0


def test_painting_skin_over_eyes_reads_as_closed(sensor):
    import numpy as np
    img = cv2.imread(str(SAMPLE))
    o, dbg = _obs(sensor, img, 10.0)
    pts = np.array(dbg.eye_pts)
    H, W = img.shape[:2]
    out = img.copy()
    for grp in (pts[:6], pts[6:]):
        x0, y0 = grp.min(0).astype(int); x1, y1 = grp.max(0).astype(int)
        b = (max(0, x0 - 6), max(0, y0 - 6), min(W, x1 + 6), min(H, y1 + 6))
        skin = img[min(H - 1, b[3] + 20):min(H, b[3] + 30), b[0]:b[2]].reshape(-1, 3).mean(0)
        out[b[1]:b[3], b[0]:b[2]] = skin
    c, _ = _obs(sensor, out, 20.0)
    assert c.face and c.ear < 0.6 * o.ear                # EAR giảm rõ rệt => dưới ngưỡng nhắm mắt 0,5
    assert c.eyes_observable                             # mi mắt nhắm (da phẳng) PHẢI vẫn quan sát được


def test_no_face_returns_unknown(sensor):
    import numpy as np
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    o, _ = sensor.process(blank, 30.0)
    assert not o.face and o.ear is None and not o.eyes_observable


def test_dark_eyes_not_observable(sensor):
    """Kính râm/thiếu sáng: vùng mắt quá tối hoặc phẳng thì KHÔNG BIẾT."""
    import numpy as np
    img = cv2.imread(str(SAMPLE))
    o, dbg = _obs(sensor, img, 40.0)
    pts = np.array(dbg.eye_pts)
    out = img.copy()
    for grp in (pts[:6], pts[6:]):
        x0, y0 = grp.min(0).astype(int); x1, y1 = grp.max(0).astype(int)
        out[max(0, y0 - 8):y1 + 8, max(0, x0 - 8):x1 + 8] = 8          # kính râm đen
    c, _ = _obs(sensor, out, 50.0)
    if c.face:                                                           # mô hình vẫn có thể tìm thấy mặt
        assert not c.eyes_observable
