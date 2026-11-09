"""Kịch bản đầu-cuối cho DecisionEngine bằng chuỗi quan sát tổng hợp."""
import pytest

from drivefocus.engine import DecisionEngine
from drivefocus.types import Context, MOVING, STOPPED

from helpers import EAR_CLOSED, EAR_OPEN, FPS, first_time, quick_cfg, run, warm_up


def new_engine(**over):
    return DecisionEngine(quick_cfg(**over))


def test_warmup_reaches_moving_and_calibrates():
    e = new_engine()
    ds = run(e, 12, 0.0, 50.0)
    assert ds[-1].moving_state == MOVING
    assert ds[-1].eye_calibrated and ds[-1].head_calibrated
    assert max(d.level for d in ds) == 0


def test_eyes_closed_3s_is_level4_and_not_before():
    """Yêu cầu chính: nhắm mắt liên tục 3 s ở tốc độ đô thị => mức 4."""
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 4.0, t0, 50.0, lambda s: {"ear": EAR_CLOSED})
    t4 = first_time(ds, lambda d: d.level == 4)
    assert t4 is not None
    assert t4 - t0 == pytest.approx(3.0, abs=0.15)
    # các mức thấp hơn đến trước, đúng ngưỡng 0,5 / 1,0 / 2,0 s
    for lvl, expect in ((1, 0.5), (2, 1.0), (3, 2.0)):
        tt = first_time(ds, lambda d, L=lvl: d.level >= L)
        assert tt - t0 == pytest.approx(expect, abs=0.15)
    assert not any(d.level == 4 for d in ds if d.t - t0 < 2.8)


def test_normal_blinks_never_alert():
    e = new_engine()
    t0 = warm_up(e)
    # chớp mắt 0,25 s mỗi 3 s trong 60 s
    ds = run(e, 60, t0, 50.0, lambda s: {"ear": EAR_CLOSED if (s % 3.0) < 0.25 else EAR_OPEN})
    assert max(d.level for d in ds) == 0
    assert not e.flush()


def test_no_alerts_when_stopped():
    e = new_engine()
    ds = run(e, 30, 0.0, 0.0, lambda s: {"ear": EAR_CLOSED})
    assert all(d.level == 0 and d.moving_state == STOPPED for d in ds)


def test_stopping_clears_active_alert():
    e = new_engine()
    t0 = warm_up(e)
    run(e, 3.5, t0, 50.0, lambda s: {"ear": EAR_CLOSED})
    ds = run(e, 8.0, t0 + 3.5, 0.0, lambda s: {"ear": EAR_CLOSED})
    # exit_hold_s = 5 s: sau đó xe coi là dừng và mức về 0
    assert ds[-1].level == 0 and ds[-1].moving_state == STOPPED


def test_face_lost_is_not_eyes_closed_but_triggers_no_face():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 20.0, t0, 50.0, lambda s: {"face": False, "ear": None, "eyes_observable": False,
                                            "yaw": None, "pitch": None, "mar": None})
    assert max(d.levels["EYES_CLOSED"] for d in ds) == 0
    assert first_time(ds, lambda d: d.levels["NO_FACE"] >= 2) - t0 == pytest.approx(5.0, abs=0.3)
    assert first_time(ds, lambda d: d.levels["NO_FACE"] >= 3) - t0 == pytest.approx(15.0, abs=0.3)
    assert max(d.level for d in ds) == 3


def test_sunglasses_eyes_unobservable_no_alert():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 20.0, t0, 50.0, lambda s: {"ear": EAR_CLOSED, "eyes_observable": False})
    assert max(d.level for d in ds) == 0
    assert "EYES_UNOBSERVABLE" in ds[-1].flags


def test_look_away_escalates_by_budget():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 7.0, t0, 50.0, lambda s: {"yaw": 45.0})
    for lvl, expect in ((1, 1.5), (2, 2.5), (3, 4.0), (4, 6.0)):
        tt = first_time(ds, lambda d, L=lvl: d.level >= L)
        assert tt is not None and tt - t0 == pytest.approx(expect, abs=0.2), (lvl, tt)


def test_quick_mirror_glance_is_ignored():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 10.0, t0, 50.0, lambda s: {"yaw": 45.0 if 2.0 <= s < 2.8 else 0.0})
    assert max(d.level for d in ds) == 0


def test_texting_with_glances_still_escalates():
    """Nhắn tin xen kẽ liếc đường: ngân sách không reset nên vẫn bị cảnh báo."""
    e = new_engine()
    t0 = warm_up(e)
    # 2 s cúi xuống, 0,3 s nhìn đường, lặp lại
    ds = run(e, 14.0, t0, 50.0, lambda s: {"pitch": 40.0 if (s % 2.3) < 2.0 else 0.0})
    assert max(d.level for d in ds) >= 3


def test_phone_hand_rule_gives_phone_event():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 6.0, t0, 50.0, lambda s: {"hand_ear": 0.3, "hand_mouth": 1.4, "hand_eye": 1.2, "hands_visible": True})
    assert max(d.levels["PHONE"] for d in ds) >= 2
    evs = [ev for d in ds for ev in d.new_events] + e.flush()
    assert any(ev["type"] == "PHONE" for ev in evs)


def test_perclos_alert_when_drowsy_pattern():
    e = new_engine()
    t0 = warm_up(e)
    # 20 s cửa sổ: nhắm 0,9 s (không đủ mức 1 theo run? 0,9 >= 0,5 là mức 1) mỗi 4 s => PERCLOS ~ 0,22
    ds = run(e, 40.0, t0, 50.0, lambda s: {"ear": EAR_CLOSED if (s % 4.0) < 0.9 else EAR_OPEN})
    assert max(d.levels["PERCLOS_HIGH"] for d in ds) >= 2


def test_head_slump_with_closed_eyes_is_level4():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 3.0, t0, 50.0, lambda s: {"ear": EAR_CLOSED, "pitch": min(30.0, 15.0 * s)})
    assert first_time(ds, lambda d: d.level == 4) is not None
    assert first_time(ds, lambda d: d.level == 4) - t0 < 2.6   # sớm hơn 3 s nhờ gục đầu


def test_event_is_emitted_with_duration_and_distance():
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 4.0, t0, 54.0, lambda s: {"ear": EAR_CLOSED})
    ds += run(e, 4.0, t0 + 4.0, 54.0)
    evs = [ev for d in ds for ev in d.new_events]
    closed = [ev for ev in evs if ev["type"] == "EYES_CLOSED"]
    assert len(closed) == 1
    ev = closed[0]
    assert ev["level"] == 4
    assert ev["schema"] == "df.event.v1"
    assert 3000 <= ev["duration_ms"] <= 4500
    # 54 km/h = 15 m/s, ~3,7 s => khoảng 55 m
    assert 45 <= ev["distance_m"] <= 65
    assert "device_id" not in ev


def test_speed_scaling_is_off_by_default_and_works_when_enabled():
    e = new_engine()
    t0 = warm_up(e, speed=100.0)
    ds = run(e, 3.5, t0, 100.0, lambda s: {"ear": EAR_CLOSED})
    assert first_time(ds, lambda d: d.level == 4) - t0 == pytest.approx(3.0, abs=0.15)

    e2 = new_engine(speed_scaling={"enabled": True})
    t0 = warm_up(e2, speed=100.0)
    ds = run(e2, 3.0, t0, 100.0, lambda s: {"ear": EAR_CLOSED})
    assert first_time(ds, lambda d: d.level == 4) - t0 == pytest.approx(1.5, abs=0.15)


def test_overspeed_context_raises_level_by_one():
    e = new_engine()
    t0 = warm_up(e)
    ctx = Context(speed_limit_kmh=40.0, congestion="FREE")
    ds = run(e, 1.2, t0, 60.0, lambda s: {"ear": EAR_CLOSED}, ctx)   # EYES_CLOSED mức 2 (1,0 s)
    assert ds[-1].raw_level == 3
    e2 = new_engine()
    t0 = warm_up(e2)
    ds2 = run(e2, 1.2, t0, 60.0, lambda s: {"ear": EAR_CLOSED}, None)
    assert ds2[-1].raw_level == 2


def test_alert_steps_down_slowly():
    e = new_engine()
    t0 = warm_up(e)
    run(e, 2.6, t0, 50.0, lambda s: {"ear": EAR_CLOSED})                       # tới mức 3
    ds = run(e, 26.0, t0 + 2.6, 50.0)                                           # mở mắt
    levels = [d.level for d in ds]
    assert levels[0] >= 2                      # không rơi thẳng về 0
    # PERCLOS cửa sổ 20 s còn cao ngay sau cơn nhắm mắt nên mức 1 kéo dài; hết cửa sổ thì về 0
    assert levels[-1] == 0
    assert all(a - b <= 1 for a, b in zip(levels, levels[1:]))   # chỉ hạ từng bậc, không tụt thẳng
    assert max(levels[90:]) <= 1                                  # sau ~6 s (2+1+1 s giữ) chỉ còn PERCLOS mức 1


def test_unknown_motion_keeps_only_level4_policy():
    """Mất GPS lâu và không có IMU: chỉ mức 4 (nhắm mắt >= 3 s) còn hiệu lực, mức 1..3 bị tắt."""
    e = new_engine()
    t0 = warm_up(e)
    ds = run(e, 38.0, t0, None, lambda s: {"ear": EAR_CLOSED if s > 31.0 else EAR_OPEN})
    unk = [d for d in ds if d.moving_state == "UNKNOWN"]
    assert unk
    assert all(d.raw_level in (0, 4) for d in unk)
    t4 = first_time(unk, lambda d: d.raw_level == 4)
    assert t4 is not None and t4 - t0 == pytest.approx(31.0 + 3.0, abs=0.4)
