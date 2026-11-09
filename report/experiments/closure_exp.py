"""Thí nghiệm thời lượng nhắm mắt trên đặc trưng THẬT lấy từ ảnh mẫu (mắt mở và mắt phủ da).

Hai ảnh (mở/nhắm) đi qua MediaPipe một lần để lấy FrameObs thật; sau đó dựng chuỗi theo thời gian
(15 khung/giây) cho từng thời lượng nhắm mắt rồi chạy DecisionEngine. Đây là thí nghiệm TỔNG HỢP trên
MỘT người: nó kiểm tra logic ngưỡng và độ trễ, không phải độ chính xác ngoài đời.

    python closure_exp.py
"""
import json
import random
import statistics
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "report" / "results"
FPS = 15.0


def real_features():
    from drivefocus.config import load_config
    from drivefocus.perception import MediaPipeSensor
    sensor = MediaPipeSensor(load_config(), ROOT / "edge" / "models")
    img = cv2.imread(str(ROOT / "edge" / "models" / "samples" / "portrait.jpg"))
    H, W = img.shape[:2]
    for i in range(3):
        obs_open, dbg = sensor.process(img, 0.1 * i)
    pts = np.array(dbg.eye_pts)
    closed = img.copy()
    for grp in (pts[:6], pts[6:]):
        x0, y0 = grp.min(0).astype(int)
        x1, y1 = grp.max(0).astype(int)
        b = (max(0, x0 - 6), max(0, y0 - 6), min(W, x1 + 6), min(H, y1 + 6))
        skin = img[min(H - 1, b[3] + 20):min(H, b[3] + 30), b[0]:b[2]].reshape(-1, 3).mean(0)
        closed[b[1]:b[3], b[0]:b[2]] = skin
        closed[b[1]:b[3], b[0]:b[2]] = cv2.GaussianBlur(closed[b[1]:b[3], b[0]:b[2]], (9, 9), 0)
    for i in range(3):
        obs_closed, _ = sensor.process(closed, 10 + 0.1 * i)
    sensor.close()
    return obs_open, obs_closed


def build(obs_open, obs_closed, closed_s, open_before=14.0, open_after=8.0, noise=0.0, dropout=0.0, seed=0, speed=50.0):
    from drivefocus.types import MotionObs
    rng = random.Random(seed)
    frames = []
    n_before, n_closed, n_after = int(open_before * FPS), int(round(closed_s * FPS)), int(open_after * FPS)
    for i in range(n_before + n_closed + n_after):
        t = i / FPS
        base = obs_closed if n_before <= i < n_before + n_closed else obs_open
        o = replace(base, t=t)
        if o.ear is not None and noise:
            o = replace(o, ear=max(0.0, o.ear + rng.gauss(0, noise)))
        if dropout and rng.random() < dropout:
            o = replace(o, face=False, ear=None, eyes_observable=False, yaw=None, pitch=None, mar=None)
        frames.append((o, MotionObs(t, speed_kmh=speed)))
    return frames, n_before / FPS


def run(frames, t_closed_start, cfg):
    from drivefocus.engine import DecisionEngine
    from drivefocus.replay import FIXED_WALL_T0
    e = DecisionEngine(cfg, wall_t0=FIXED_WALL_T0)
    first = {}
    maxlvl = 0
    events = []
    for obs, motion in frames:
        d = e.update(obs, motion)
        events += d.new_events
        maxlvl = max(maxlvl, d.level)
        for L in (1, 2, 3, 4):
            if d.level >= L and L not in first:
                first[L] = d.t - t_closed_start
    events += e.flush()
    n_closed_events = sum(1 for ev in events if ev["type"] == "EYES_CLOSED")
    return maxlvl, first, n_closed_events


def main():
    from drivefocus.config import load_config, quick_demo_overrides
    obs_open, obs_closed = real_features()
    print(f"EAR mở = {obs_open.ear:.3f}, EAR nhắm = {obs_closed.ear:.3f}, tỉ lệ = {obs_closed.ear / obs_open.ear:.2f}")
    base_over = quick_demo_overrides()
    cfg = load_config(overrides=base_over)
    cfg_scale = load_config(overrides={**base_over, "speed_scaling": {"enabled": True}})

    durations = [0.2, 0.4, 0.6, 1.0, 1.5, 2.0, 2.5, 2.9, 3.0, 3.5, 4.5]
    res = {"ear_open": obs_open.ear, "ear_closed": obs_closed.ear, "rows": [], "robust": [], "scaling": [], "stopped": None}
    for d in durations:
        frames, t0 = build(obs_open, obs_closed, d)
        mx, first, n = run(frames, t0, cfg)
        res["rows"].append({"closed_s": d, "max_level": mx, "first_s": first, "eyes_closed_events": n})
        print(f"nhắm {d:>4} s -> mức tối đa {mx}, thời điểm đạt: {{{', '.join(f'L{k}:{v:.2f}s' for k, v in first.items())}}}, sự kiện {n}")

    # độ bền: nhiễu EAR sigma 0,02 và mất mặt ngẫu nhiên 3% khung, 20 hạt giống
    for d in (0.3, 1.0, 3.5):
        mxs, l4 = [], 0
        for seed in range(20):
            frames, t0 = build(obs_open, obs_closed, d, noise=0.02, dropout=0.03, seed=seed)
            mx, first, n = run(frames, t0, cfg)
            mxs.append(mx)
            l4 += mx == 4
        res["robust"].append({"closed_s": d, "runs": 20, "level4_runs": l4, "mean_max_level": statistics.mean(mxs),
                              "max_levels": mxs})
        print(f"[nhiễu+mất mặt] nhắm {d} s: mức 4 trong {l4}/20 lần, mức tối đa trung bình {statistics.mean(mxs):.2f}")

    # hệ số tốc độ (thí nghiệm tùy chọn)
    for speed in (50.0, 100.0):
        for d in (1.0, 1.5, 2.0, 3.0):
            row = {"speed": speed, "closed_s": d}
            for name, c in (("off", cfg), ("on", cfg_scale)):
                frames, t0 = build(obs_open, obs_closed, d + 0.6, speed=speed)
                frames, t0 = build(obs_open, obs_closed, d, speed=speed)
                mx, first, n = run(frames, t0, c)
                row[name] = {"max_level": mx, "t_l4": first.get(4)}
            res["scaling"].append(row)
            print(f"v={speed:.0f} nhắm {d}s: tắt hệ số -> L{row['off']['max_level']} (L4 @ {row['off']['t_l4']}), bật -> L{row['on']['max_level']} (L4 @ {row['on']['t_l4']})")

    # xe đang dừng: nhắm mắt 10 s không được báo
    frames, t0 = build(obs_open, obs_closed, 10.0, open_before=14.0, speed=0.0)
    mx, first, n = run(frames, t0, cfg)
    res["stopped"] = {"closed_s": 10.0, "max_level": mx, "events": n}
    print("xe dừng, nhắm 10 s: mức tối đa", mx, "sự kiện", n)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "closure.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
