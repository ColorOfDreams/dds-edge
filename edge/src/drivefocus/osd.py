"""Vẽ lớp thông tin lên khung hình (OpenCV chỉ vẽ được ASCII nên nhãn không dấu)."""
from __future__ import annotations

from .hal import LEVEL_TEXT
from .types import Decision, FrameObs

# BGR
LEVEL_COLORS = {0: (60, 180, 75), 1: (0, 215, 255), 2: (0, 140, 255), 3: (40, 40, 230), 4: (0, 0, 255)}


def draw(frame, obs: FrameObs, dec: Decision, dbg, speed_kmh: float, mute: bool, pose_ok: bool = True):
    import cv2

    h, w = frame.shape[:2]
    color = LEVEL_COLORS[dec.level]

    if dbg is not None:
        for (x, y) in dbg.eye_pts:
            cv2.circle(frame, (int(x), int(y)), 1, (255, 255, 0), -1)
        for (x, y) in dbg.mouth_pts:
            cv2.circle(frame, (int(x), int(y)), 2, (255, 0, 255), -1)
        for (x, y) in dbg.hand_centers:
            cv2.circle(frame, (int(x), int(y)), 8, (0, 255, 255), 2)
        if dbg.face_box:
            x0, y0, x1, y1 = [int(v) for v in dbg.face_box]
            cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)

    # thanh mức
    cv2.rectangle(frame, (0, 0), (w, 34), color, -1)
    label = f"LEVEL {dec.level}  {LEVEL_TEXT[dec.level]}" if dec.level else "OK"
    cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if dec.level == 4 and int(dec.t * 4) % 2 == 0:
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (0, 0, 255), 8)

    ear = "-" if dec.ear is None else f"{dec.ear:.2f}"
    ear_n = "-" if dec.ear_norm is None else f"{dec.ear_norm:.2f}"
    lines = [
        f"{dec.moving_state}  speed {speed_kmh:.0f} km/h" + ("  [MUTE]" if mute else ""),
        f"EAR {ear} (norm {ear_n})  closed {dec.closure_run:.1f}s",
        f"PERCLOS {dec.perclos * 100:.0f}%" + ("" if dec.perclos_ready else " (warming up)")
        + f"  yawns {dec.yawns_10min}",
        "pose d_yaw %s d_pitch %s" % (
            "-" if dec.dyaw is None else f"{dec.dyaw:+.0f}",
            "-" if dec.dpitch is None else f"{dec.dpitch:+.0f}"),
        f"attention {dec.budget * 100:.0f}%",
    ]
    for key in ("EYE_UNCALIBRATED", "HEAD_UNCALIBRATED"):
        if key in dec.flags:
            lines.append(key.replace("_", " ").lower() + " (press C)")
    for flag in ("NO_FACE", "EYES_UNOBSERVABLE"):
        if flag in dec.flags:
            lines.append(flag + " -> unknown, no inference")
    y = 56
    for line in lines:
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 20

    # thanh ngân sách chú ý
    bar_w = 140
    cv2.rectangle(frame, (w - bar_w - 12, 44), (w - 12, 60), (50, 50, 50), -1)
    cv2.rectangle(frame, (w - bar_w - 12, 44), (w - 12 - int(bar_w * (1 - dec.budget)), 60), (0, 0, 0), -1)
    cv2.rectangle(frame, (w - 12 - int(bar_w * dec.budget), 44), (w - 12, 60), color, -1)

    cv2.putText(frame, "q quit | w/s speed +-10 | space stop/go | c calibrate | m mute | g gaze",
                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    return frame
