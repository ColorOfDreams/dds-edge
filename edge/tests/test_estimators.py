import pytest

from drivefocus.config import load_config
from drivefocus.estimators import AttentionBudget, EyeEstimator, HandEstimator, HeadEstimator, YawnEstimator
from drivefocus.motion import MovementGate
from drivefocus.types import MOVING, STOPPED, UNKNOWN

from helpers import FPS, quick_cfg


# ----------------------------------------------------------- cổng chuyển động
def test_gate_hysteresis():
    gate = MovementGate(load_config())
    t = 0.0
    seq = []
    # dưới ngưỡng vào: không chạy
    for _ in range(100):
        seq.append(gate.update(t, 8.0)); t += 0.1
    assert set(seq) == {STOPPED}
    # chạm ngưỡng nhưng chưa đủ 3 s
    for _ in range(25):
        assert gate.update(t, 12.0) == STOPPED; t += 0.1
    for _ in range(10):
        state = gate.update(t, 12.0); t += 0.1
    assert state == MOVING
    # kẹt xe 5 km/h: vẫn MOVING vì chưa xuống dưới 3 km/h
    for _ in range(100):
        assert gate.update(t, 5.0) == MOVING; t += 0.1
    # dừng thật: 2 km/h trong 4 s vẫn MOVING, đủ 5 s thì STOPPED
    for _ in range(40):
        assert gate.update(t, 2.0) == MOVING; t += 0.1
    for _ in range(15):
        state = gate.update(t, 2.0); t += 0.1
    assert state == STOPPED


def test_gate_gps_loss():
    gate = MovementGate(load_config())
    t = 0.0
    for _ in range(50):
        gate.update(t, 40.0); t += 0.1
    assert gate.state == MOVING
    # mất GPS 20 s: giữ MOVING; quá 30 s mà không có IMU: UNKNOWN
    assert gate.update(t + 20, None) == MOVING
    assert gate.update(t + 31, None) == UNKNOWN
    # có IMU thì dùng IMU
    assert gate.update(t + 32, None, vibration=0.5) == MOVING
    assert gate.update(t + 33, None, vibration=0.01) == STOPPED


# ----------------------------------------------------------------------- mắt
def _feed(est, t0, seconds, ear, observable=True, face=True, allow=True):
    t = t0
    state = None
    for _ in range(int(seconds * FPS)):
        state = est.update(t, face, ear, observable, allow)
        t += 1 / FPS
    return t, state


def test_closure_run_counts_continuous_closure():
    est = EyeEstimator(quick_cfg())
    t, _ = _feed(est, 0, 6, 0.30)               # hiệu chỉnh xong (calibration_s=5)
    assert est.baseline == pytest.approx(0.30)
    t, st = _feed(est, t, 3.0, 0.05)
    assert st.closure_run == pytest.approx(3.0, abs=0.1)


def test_blink_does_not_reach_level1_and_resets():
    est = EyeEstimator(quick_cfg())
    t, _ = _feed(est, 0, 6, 0.30)
    t, st = _feed(est, t, 0.3, 0.05)            # chớp mắt 0,3 s
    assert st.closure_run < 0.5
    t, st = _feed(est, t, 0.5, 0.30)            # mở mắt quá 0,2 s => reset
    assert st.closure_run == 0.0


def test_short_gap_does_not_reset_run():
    est = EyeEstimator(quick_cfg())
    t, _ = _feed(est, 0, 6, 0.30)
    t, _ = _feed(est, t, 1.0, 0.05)
    t, st = _feed(est, t, 2 / FPS, 0.30)        # nhiễu 2 khung "mở"
    t, st = _feed(est, t, 1.0, 0.05)
    assert st.closure_run > 2.0                 # vẫn tính liên tục


def test_unknown_does_not_count_as_closed():
    """Không thấy mắt (kính râm, mất mặt) tuyệt đối không được suy ra nhắm mắt."""
    est = EyeEstimator(quick_cfg())
    t, _ = _feed(est, 0, 6, 0.30)
    t, st = _feed(est, t, 10.0, None, observable=False)
    assert st.closed is None and st.closure_run == 0.0
    t, st = _feed(est, t, 10.0, 0.30, face=False)
    assert st.closure_run == 0.0


def test_perclos_time_weighted_and_excludes_unknown():
    est = EyeEstimator(quick_cfg())
    t, _ = _feed(est, 0, 6, 0.30)
    # cửa sổ 20 s: 15 s mở rồi 5 s nhắm => PERCLOS 0,25 khi cửa sổ đầy
    t, _ = _feed(est, t, 15, 0.30)
    t, st = _feed(est, t, 5, 0.05)
    assert st.perclos_ready
    assert st.perclos == pytest.approx(0.25, abs=0.06)
    # khoảng KHÔNG BIẾT không làm thay đổi tỉ lệ
    est2 = EyeEstimator(quick_cfg())
    t, _ = _feed(est2, 0, 6, 0.30)
    t, _ = _feed(est2, t, 12, 0.30)
    t, _ = _feed(est2, t, 4, None, observable=False)
    t, st2 = _feed(est2, t, 4, 0.05)
    assert st2.perclos == pytest.approx(4 / (12 + 4) * 1.0, abs=0.08) or st2.perclos < 0.35


def test_perclos_not_ready_until_window_full():
    est = EyeEstimator(quick_cfg())
    t, st = _feed(est, 0, 8, 0.30)
    assert not st.perclos_ready


def test_calibration_rejects_nonsense_baseline():
    est = EyeEstimator(quick_cfg())
    _feed(est, 0, 8, 0.80)                       # EAR vô lý
    assert est.baseline is None                  # giữ ngưỡng tuyệt đối


# -------------------------------------------------------------------- ngáp
def test_yawn_counts_sustained_mouth_opening_only():
    y = YawnEstimator(load_config())
    t = 0.0
    for _ in range(int(1.0 * FPS)):              # há 1 s: chưa phải ngáp
        assert not y.update(t, True, 0.8); t += 1 / FPS
    y.update(t, True, 0.05); t += 1 / FPS
    assert y.count(t) == 0
    new = False
    for _ in range(int(2.0 * FPS)):              # há 2 s: ngáp
        new |= y.update(t, True, 0.8); t += 1 / FPS
    assert new and y.count(t) == 1


# ----------------------------------------------------------- tư thế đầu
def test_head_neutral_and_off_road():
    h = HeadEstimator(quick_cfg())
    t = 0.0
    for _ in range(int(6 * FPS)):                # 6 s nhìn thẳng ở tốc độ cao => hiệu chỉnh
        st = h.update(t, 5.0, 10.0, None, 50.0); t += 1 / FPS
    assert st.calibrated and h.neutral == pytest.approx((5.0, 10.0))
    st = h.update(t, 5.0 + 40, 10.0, None, 50.0)
    assert st.off_road and st.dyaw == pytest.approx(40)
    st = h.update(t + 0.1, 5.0, 10.0 + 30, None, 50.0)
    assert st.off_road and st.dpitch == pytest.approx(30)
    st = h.update(t + 0.2, 5.0 - 10, 10.0, None, 50.0)
    assert not st.off_road


def test_head_uncalibrated_uses_wider_threshold():
    h = HeadEstimator(quick_cfg())
    st = h.update(0.0, 35.0, 0.0, None, 10.0)   # 35° < 30*1.5 => chưa tính là lệch
    assert not st.calibrated and not st.off_road


def test_head_nod_detection():
    h = HeadEstimator(quick_cfg())
    t = 0.0
    for _ in range(int(6 * FPS)):
        h.update(t, 0.0, 0.0, None, 50.0); t += 1 / FPS
    st = None
    for p in (0, 5, 10, 18, 25):                 # cúi nhanh 25° trong ~0,3 s
        st = h.update(t, 0.0, float(p), None, 50.0); t += 0.07
    assert st.nod


# -------------------------------------------------------------------- bàn tay
def test_hand_phone_rule_needs_duration_and_ignores_eye_rubbing():
    est = HandEstimator(load_config())
    t = 0.0
    res = {}
    for _ in range(int(1.0 * FPS)):
        res = est.update(t, True, 0.3, 1.5, 1.2, True); t += 1 / FPS
    assert not res["phone"]                      # mới 1 s
    for _ in range(int(1.0 * FPS)):
        res = est.update(t, True, 0.3, 1.5, 1.2, True); t += 1 / FPS
    assert res["phone"] and not res["mouth"]
    # dụi mắt: tay gần mắt hơn tai/miệng
    est2 = HandEstimator(load_config())
    for _ in range(int(4 * FPS)):
        res = est2.update(t, True, 0.5, 0.5, 0.2, True); t += 1 / FPS
    assert not res["phone"] and not res["mouth"]


# ------------------------------------------------------ ngân sách chú ý
def test_budget_levels_at_documented_times():
    b = AttentionBudget(load_config())
    t = 0.0
    first = {}
    while t < 6.5:
        a, lvl, _ = b.update(t, {"look_away": True, "phone": False, "mouth": False})
        for L in (1, 2, 3, 4):
            if lvl >= L and L not in first:
                first[L] = t
        t += 0.02
    assert first[1] == pytest.approx(1.5, abs=0.1)
    assert first[2] == pytest.approx(2.5, abs=0.1)
    assert first[3] == pytest.approx(4.0, abs=0.1)
    assert first[4] == pytest.approx(6.0, abs=0.1)


def test_budget_phone_weighs_more_and_recovery_is_gradual():
    b = AttentionBudget(load_config())
    t = 0.0
    while b.level() < 4 and t < 10:
        b.update(t, {"look_away": False, "phone": True, "mouth": False}); t += 0.02
    assert t == pytest.approx(4.0, abs=0.15)     # 6 s / 1.5
    # liếc đường 0,5 s rồi lại nhìn điện thoại: ngân sách không reset về đầy
    a_before = 0.2
    b.a = a_before
    b.update(t, {"look_away": False, "phone": False, "mouth": False})
    b.update(t + 0.5, {"look_away": False, "phone": False, "mouth": False})
    assert b.a < 1.0
