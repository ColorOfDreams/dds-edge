"""Sinh hình cho báo cáo và slide. Dùng: python make_figs.py [tên nhóm ...]
Nhóm: arch fsm budget closure signals osd bench sf
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "report" / "results"
FIG = ROOT / "report" / "figs"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 100, "savefig.dpi": 200,
                     "axes.unicode_minus": False})
NAVY, TEAL, ORANGE, RED, GREY, GREEN = "#1F3A5F", "#1B998B", "#F28F3B", "#C8283C", "#8C8C8C", "#4C9F70"
LEVEL_COL = {0: GREEN, 1: "#F2C94C", 2: ORANGE, 3: "#E5533D", 4: RED}


def _find_dds(root):
    """dds-edge nằm cạnh drivefocus/ (bản làm việc) hoặc chính là thư mục cha (nhánh drive-focus của repo dds-edge)."""
    for cand in (root.parent / "dds-edge", root.parent):
        if (cand / "src" / "dds_edge").is_dir():
            return cand
    return root.parent / "dds-edge"


def box(ax, x, y, w, h, text, fc="#EEF2F7", ec=NAVY, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal",
            wrap=True)


def arrow(ax, p, q, text=None, color=NAVY, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=1.2, color=color,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 0.08, text, ha="center", fontsize=8, color=color)


def fig_arch():
    fig, ax = plt.subplots(figsize=(6.6, 4.1))
    ax.set_xlim(0, 11.2); ax.set_ylim(0.2, 6.5); ax.axis("off")
    white = dict(fc="white", ec="none", pad=1.5)
    ax.add_patch(FancyBboxPatch((0.1, 0.75), 6.6, 5.6, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#F7F9FC", ec=GREY, ls="--"))
    ax.text(0.3, 6.05, "Trên xe: DF-Edge (K230 hoặc giả lập trên PC)", fontsize=9, color=NAVY, fontweight="bold")
    box(ax, 0.3, 4.75, 1.4, 0.95, "Camera\n(IR)", fs=8.5)
    box(ax, 2.0, 4.75, 2.1, 0.95, "Cảm biến thị giác\nmặt, điểm mốc, tay", fc="#E3F4F1", ec=TEAL, fs=8.5)
    box(ax, 4.4, 4.75, 2.1, 0.95, "Số đo\nEAR, MAR, pose", fc="#E3F4F1", ec=TEAL, fs=8.5)
    arrow(ax, (1.7, 5.22), (2.0, 5.22)); arrow(ax, (4.1, 5.22), (4.4, 5.22))
    box(ax, 0.3, 3.1, 1.7, 1.05, "GPS + IMU\n(chuyển\nđộng)", fs=8.5)
    box(ax, 2.4, 3.1, 4.1, 1.05, "Thuật toán quyết định\n(tự viết, 4 mức)", fc="#FDEBD3", ec=ORANGE, bold=True, fs=8.5)
    arrow(ax, (2.0, 3.62), (2.4, 3.62)); arrow(ax, (5.45, 4.75), (5.45, 4.15))
    box(ax, 0.3, 1.5, 1.7, 0.6, "Còi, LED", fc="#FBE3E3", ec=RED, fs=8.5)
    box(ax, 4.4, 1.5, 2.1, 0.6, "Hàng đợi sự kiện", fs=8.5)
    arrow(ax, (3.2, 3.1), (1.7, 2.1)); arrow(ax, (5.45, 3.1), (5.45, 2.1))
    ax.text(0.3, 1.0, "Không có video rời thiết bị", fontsize=8.5, color=RED, style="italic")
    box(ax, 7.7, 4.6, 2.5, 1.15, "device-gateway\nẩn danh hóa:\ndriver_id = trip_id", fc="#E8EEF9", fs=8.5)
    box(ax, 7.7, 2.6, 2.5, 1.15, "Traffic-SM\ngps.raw → gps.matched\n→ mức tắc nghẽn", fc="#E8EEF9", fs=8)
    box(ax, 7.7, 0.6, 2.5, 1.15, "ClickHouse df.events\n+ Grafana", fc="#E8EEF9", fs=8.5)
    ax.plot([6.5, 7.2, 7.2], [1.8, 1.8, 5.17], color=NAVY, lw=1.2); arrow(ax, (7.2, 5.17), (7.7, 5.17))
    ax.text(7.2, 1.35, "HTTP", fontsize=8, color=NAVY, ha="center", bbox=white)
    arrow(ax, (8.95, 4.6), (8.95, 3.75)); ax.text(9.05, 4.15, "GPS", fontsize=8, color=NAVY)
    ax.plot([10.2, 10.7, 10.7], [5.17, 5.17, 1.17], color=NAVY, lw=1.2); arrow(ax, (10.7, 1.17), (10.2, 1.17))
    ax.text(10.7, 3.2, "sự kiện", rotation=90, fontsize=8, color=NAVY, ha="center", va="center", bbox=white)
    arrow(ax, (7.7, 3.2), (6.5, 3.5), color=GREY); ax.text(7.2, 3.95, "ngữ cảnh đường", fontsize=7.5, color=GREY, ha="center", bbox=white)
    fig.savefig(FIG / "arch.png", bbox_inches="tight"); plt.close(fig)


def fig_ear():
    import numpy as np
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    ax.set_aspect("equal"); ax.axis("off")
    x = np.linspace(0, 6, 200)
    ax.plot(x, 0.9 * np.sin(np.pi * x / 6) ** 0.8 * 1.0, color=NAVY, lw=2)
    ax.plot(x, -0.9 * np.sin(np.pi * x / 6) ** 0.8 * 0.85, color=NAVY, lw=2)
    pts = {"p1": (0, 0), "p4": (6, 0), "p2": (2.0, 0.93 * np.sin(np.pi * 2 / 6) ** 0.8), "p3": (4.0, 0.93 * np.sin(np.pi * 4 / 6) ** 0.8),
           "p6": (2.0, -0.77 * np.sin(np.pi * 2 / 6) ** 0.8), "p5": (4.0, -0.77 * np.sin(np.pi * 4 / 6) ** 0.8)}
    for k, (px, py) in pts.items():
        ax.plot(px, py, "o", color=RED, ms=6)
        ax.text(px + (-0.28 if k in ("p1",) else 0.12 if k != "p4" else 0.12), py + (0.12 if py >= 0 else -0.22), k, fontsize=10)
    ax.plot([2.0, 2.0], [pts["p6"][1], pts["p2"][1]], "--", color=GREY, lw=1)
    ax.plot([4.0, 4.0], [pts["p5"][1], pts["p3"][1]], "--", color=GREY, lw=1)
    ax.annotate("", xy=(0, -1.15), xytext=(6, -1.15), arrowprops=dict(arrowstyle="<->", color=TEAL))
    ax.text(3.0, -1.4, "‖p1 − p4‖", ha="center", fontsize=9, color=TEAL)
    ax.text(7.0, 0.35, "EAR =", fontsize=11, fontweight="bold")
    ax.text(7.0, -0.2, "‖p2 − p6‖ + ‖p3 − p5‖", fontsize=10); ax.plot([7.0, 9.75], [-0.33, -0.33], color="black", lw=0.8)
    ax.text(7.0, -0.65, "2 · ‖p1 − p4‖", fontsize=10)
    ax.set_xlim(-0.6, 10)
    fig.savefig(FIG / "ear.png", bbox_inches="tight"); plt.close(fig)


def fig_fsm():
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    ax.set_xlim(0, 10.6); ax.set_ylim(0, 4.4); ax.axis("off")
    names = [("Bình thường\n(mức 0)", GREEN), ("Nhắc nhẹ\n(mức 1)", "#F2C94C"), ("Cảnh báo\n(mức 2)", ORANGE),
             ("Nguy hiểm\n(mức 3)", "#E5533D"), ("Báo động\n(mức 4)", RED)]
    xs = [0.1, 2.2, 4.3, 6.4, 8.5]
    for (n, c), x in zip(names, xs):
        ax.add_patch(FancyBboxPatch((x, 2.0), 1.9, 1.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c, ec="white"))
        ax.text(x + 0.95, 2.65, n, ha="center", va="center", fontsize=9, color="white" if c in (RED, "#E5533D", GREEN) else "#222", fontweight="bold")
    for i in range(4):
        arrow(ax, (xs[i] + 1.9, 2.95), (xs[i + 1], 2.95))
        arrow(ax, (xs[i + 1], 2.35), (xs[i] + 1.9, 2.35), color=GREY)
    ax.text(5.3, 1.55, "mũi tên trên: lên ngay khi điều kiện đạt        mũi tên xám: xuống từng bậc sau 1 s, 1 s, 2 s, 3 s",
            ha="center", fontsize=8.3, color="#444")
    ax.add_patch(FancyBboxPatch((0.1, 0.2), 10.3, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#EEF2F7", ec=NAVY))
    ax.text(5.25, 0.68, "Xe dừng (dưới 3 km/h liên tục 5 s) → về mức 0 ngay.   Xe chạy: từ 10 km/h liên tục 3 s.",
            ha="center", va="center", fontsize=8.8)
    ax.text(5.3, 4.1, "Máy trạng thái hiển thị mức cảnh báo", ha="center", fontsize=10, fontweight="bold", color=NAVY)
    fig.savefig(FIG / "fsm.png", bbox_inches="tight"); plt.close(fig)


def fig_budget():
    sys.path.insert(0, str(ROOT / "edge" / "src"))
    from drivefocus.config import load_config
    from drivefocus.estimators import AttentionBudget
    cfg = load_config()
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.9), sharey=True)
    for ax, (title, schedule) in zip(axes, (
            ("Nhìn lệch liên tục (w = 1)", lambda t: {"look_away": True}),
            ("Nhắn tin xen kẽ liếc đường (w = 1,5)", lambda t: {"phone": (t % 2.3) < 2.0}))):
        b = AttentionBudget(cfg)
        ts, a, lv = [], [], []
        t = 0.0
        while t < 12:
            A, L, _ = b.update(t, {"look_away": False, "phone": False, "mouth": False, **schedule(t)})
            ts.append(t); a.append(A); lv.append(L)
            t += 0.02
        ax.plot(ts, a, color=NAVY, lw=1.8)
        for th, name in zip(cfg.attention_budget.levels, ("mức 1", "mức 2", "mức 3")):
            ax.axhline(th, color=GREY, lw=0.7, ls=":")
            ax.text(11.9, th + 0.01, name, ha="right", fontsize=7.5, color=GREY)
        ax.set_title(title, fontsize=9); ax.set_xlabel("thời gian (s)")
        ax.set_ylim(0, 1.03); ax.set_xlim(0, 12)
    axes[0].set_ylabel("ngân sách chú ý A")
    fig.tight_layout(); fig.savefig(FIG / "budget.png", bbox_inches="tight"); plt.close(fig)


def fig_closure():
    d = json.loads((RES / "closure.json").read_text(encoding="utf-8"))
    rows = d["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.9))
    ax = axes[0]
    xs = [r["closed_s"] for r in rows]
    ax.step(xs, [r["max_level"] for r in rows], where="post", color=NAVY, lw=1.8)
    ax.scatter(xs, [r["max_level"] for r in rows], color=[LEVEL_COL[r["max_level"]] for r in rows], zorder=3, s=28)
    ax.axvline(3.0, color=RED, ls="--", lw=1); ax.text(3.05, 0.2, "3 s", color=RED, fontsize=8)
    ax.set_xlabel("thời lượng nhắm mắt (s)"); ax.set_ylabel("mức cao nhất đạt được"); ax.set_yticks(range(5))
    ax.set_title("Mức đạt được theo thời lượng nhắm", fontsize=9)
    ax = axes[1]
    longest = [r for r in rows if r["closed_s"] == 4.5][0]
    for L, col in zip((1, 2, 3, 4), (LEVEL_COL[1], LEVEL_COL[2], LEVEL_COL[3], LEVEL_COL[4])):
        ax.barh(f"mức {L}", longest["first_s"][str(L)], color=col)
        ax.text(longest["first_s"][str(L)] + 0.05, f"mức {L}", f"{longest['first_s'][str(L)]:.2f} s", va="center", fontsize=8)
    ax.set_xlim(0, 3.7); ax.set_xlabel("độ trễ từ lúc bắt đầu nhắm (s)"); ax.set_title("Thời điểm đạt từng mức", fontsize=9)
    ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(FIG / "closure.png", bbox_inches="tight"); plt.close(fig)


def _trace_series():
    sys.path.insert(0, str(ROOT / "edge" / "src"))
    from drivefocus.config import load_config, quick_demo_overrides
    from drivefocus.engine import DecisionEngine
    from drivefocus.replay import read_trace
    cfg = load_config(overrides=quick_demo_overrides())
    e = DecisionEngine(cfg)
    t, ear, run, lvl, thr = [], [], [], [], []
    for obs, motion in read_trace(ROOT / "edge" / "out" / "trace.jsonl"):
        d = e.update(obs, motion)
        t.append(d.t); ear.append(obs.ear if obs.ear is not None else float("nan"))
        run.append(d.closure_run); lvl.append(d.level)
        thr.append(cfg.eyes.ear_closed_ratio * e.eyes.baseline if e.eyes.baseline else cfg.eyes.ear_closed_abs_fallback)
    return t, ear, run, lvl, thr


def fig_signals():
    t, ear, run, lvl, thr = _trace_series()
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 4.6), sharex=True)
    axes[0].plot(t, ear, color=NAVY, lw=1.4, label="EAR"); axes[0].plot(t, thr, color=RED, ls="--", lw=1, label="ngưỡng nhắm")
    axes[0].set_ylabel("EAR"); axes[0].legend(fontsize=8, loc="lower left", ncol=1, frameon=False)
    axes[1].plot(t, run, color=TEAL, lw=1.6); axes[1].axhline(3.0, color=RED, ls=":", lw=1); axes[1].text(0.3, 3.1, "ngưỡng mức 4 = 3 s", fontsize=8, color=RED)
    axes[1].set_ylabel("nhắm liên tục (s)")
    axes[2].step(t, lvl, where="post", color=ORANGE, lw=1.8); axes[2].set_yticks(range(5)); axes[2].set_ylabel("mức cảnh báo"); axes[2].set_xlabel("thời gian (s)")
    for ax in axes:
        ax.axvspan(14.0, 18.0, color=RED, alpha=0.06)
    axes[0].text(14.15, 0.115, "mắt nhắm (giả lập)", fontsize=8, color=RED, va="center")
    fig.tight_layout(); fig.savefig(FIG / "signals.png", bbox_inches="tight"); plt.close(fig)


def fig_osd():
    import cv2
    sys.path.insert(0, str(ROOT / "edge" / "src"))
    from drivefocus.config import load_config, quick_demo_overrides
    from drivefocus.engine import DecisionEngine
    from drivefocus.osd import draw
    from drivefocus.perception import MediaPipeSensor
    from drivefocus.types import MotionObs
    cfg = load_config(overrides=quick_demo_overrides())
    sensor = MediaPipeSensor(cfg, ROOT / "edge" / "models")
    e = DecisionEngine(cfg)
    cap = cv2.VideoCapture(str(ROOT / "edge" / "out" / "synthetic.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    want = {0: 13.0, 1: 14.0 + 0.6, 2: 14.0 + 1.1, 3: 14.0 + 2.1, 4: 14.0 + 3.1}   # thời điểm chụp gần mức mong muốn
    shots = {}
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = n / fps
        obs, dbg = sensor.process(frame, t)
        d = e.update(obs, MotionObs(t, speed_kmh=50.0))
        for lvl, tt in want.items():
            if lvl not in shots and t >= tt and d.level == lvl:
                import numpy as np
                canvas = np.zeros_like(frame)                      # chế độ riêng tư: chỉ điểm mốc, không ảnh gốc
                for (x, y) in dbg.all_pts:
                    cv2.circle(canvas, (int(x), int(y)), 1, (150, 150, 150), -1)
                shots[lvl] = draw(canvas, obs, d, dbg, 50.0, False)
        n += 1
    sensor.close()
    print("đã chụp mức:", sorted(shots))
    for lvl, im in shots.items():
        h, w = im.shape[:2]
        cv2.imwrite(str(FIG / f"osd_L{lvl}.png"), im)
    chosen = [l for l in (0, 2, 4) if l in shots]
    fig, axes = plt.subplots(1, len(chosen), figsize=(6.4, 3.05))
    for ax, l in zip(axes, chosen):
        im = shots[l]
        h, w = im.shape[:2]
        ax.imshow(cv2.cvtColor(im[: int(h * 0.60), : int(w * 0.78)], cv2.COLOR_BGR2RGB)); ax.axis("off")
        ax.set_title(f"mức {l}", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "osd_levels.png", bbox_inches="tight"); plt.close(fig)


def fig_bench():
    b = json.loads((RES / "bench.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(5.6, 2.3))
    parts = [("Cảm biến (mặt + tay, MediaPipe)", b["sensor_ms"]["mean"], TEAL), ("Thuật toán quyết định", b["engine_ms_in_loop"]["mean"], ORANGE)]
    left = 0
    for name, v, c in parts:
        ax.barh([0], [v], left=left, height=0.5, color=c, label=f"{name}: {v:.2f} ms")
        left += v
    ax.set_yticks([]); ax.set_xlabel("ms mỗi khung (CPU)")
    ax.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.38), ncol=1)
    ax.text(left + 0.4, 0, f"≈ {b['pipeline_fps']:.0f} khung/s", va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(0, left * 1.4)
    fig.tight_layout(); fig.savefig(FIG / "bench.png", bbox_inches="tight"); plt.close(fig)


def fig_sf():
    import cv2
    a = json.loads((RES / "sf_analysis.json").read_text(encoding="utf-8"))
    names = {"c0": "c0", "c1": "c1", "c2": "c2", "c3": "c3", "c4": "c4", "c5": "c5", "c6": "c6", "c7": "c7", "c8": "c8", "c9": "c9"}
    cl = list(names)
    # 1. tỉ lệ phát hiện
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    det = a["detection"]
    import numpy as np
    x = np.arange(len(cl)); w = 0.38
    ax.bar(x - w / 2, [det[c]["face"] / det[c]["n"] * 100 for c in cl], w, color=RED, label="Face Landmarker (mặt)")
    ax.bar(x + w / 2, [det[c]["pose"] / det[c]["n"] * 100 for c in cl], w, color=TEAL, label="Pose Landmarker (tai, miệng, cổ tay)")
    ax.set_xticks(x); ax.set_xticklabels(cl); ax.set_ylabel("% ảnh phát hiện được"); ax.set_ylim(0, 105)
    ax.legend(fontsize=8, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.2))
    fig.tight_layout(); fig.savefig(FIG / "sf_detection.png", bbox_inches="tight"); plt.close(fig)
    # 2. đường F1 theo ngưỡng (val)
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.7), sharey=True)
    for ax, (key, title) in zip(axes, (("phone", "Gọi điện (c2, c4): d(tay, tai)"), ("drink", "Uống nước (c6): d(tay, miệng)"))):
        r = a["rules"][key]
        ks = [s["k"] for s in r["val_sweep"]]
        ax.plot(ks, [s["precision"] for s in r["val_sweep"]], color=NAVY, label="precision")
        ax.plot(ks, [s["recall"] for s in r["val_sweep"]], color=ORANGE, label="recall")
        ax.plot(ks, [s["f1"] for s in r["val_sweep"]], color=GREEN, lw=2, label="F1")
        ax.axvline(r["best_k"], color=RED, ls="--", lw=1); ax.text(r["best_k"] + 0.03, 0.04, f"k* = {r['best_k']}", color=RED, fontsize=8)
        ax.set_xlabel("ngưỡng k (đơn vị: cỡ đầu)"); ax.set_title(title, fontsize=9)
    axes[0].set_ylabel("điểm (tập val)"); axes[0].legend(fontsize=8, frameon=False, loc="center right")
    fig.tight_layout(); fig.savefig(FIG / "sf_curves.png", bbox_inches="tight"); plt.close(fig)
    # 3. tỉ lệ gắn cờ theo lớp (test)
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    fp, fd = a["flagged_by_class"]["phone"], a["flagged_by_class"]["drink"]
    ax.bar(x - w / 2, [fp[c]["rate"] * 100 for c in cl], w, color=NAVY, label=f"luật tai (k = {a['rules']['phone']['best_k']})")
    ax.bar(x + w / 2, [fd[c]["rate"] * 100 for c in cl], w, color=ORANGE, label=f"luật miệng (k = {a['rules']['drink']['best_k']})")
    for c, col in (("c2", GREEN), ("c4", GREEN)):
        ax.annotate("", xy=(cl.index(c) - w / 2, 0), xytext=(cl.index(c) - w / 2, -9), arrowprops=dict(arrowstyle="-|>", color=GREEN))
    ax.annotate("", xy=(cl.index("c6") + w / 2, 0), xytext=(cl.index("c6") + w / 2, -9), arrowprops=dict(arrowstyle="-|>", color=GREEN))
    ax.set_xticks(x); ax.set_xticklabels(cl); ax.set_ylabel("% ảnh bị đánh dấu (tập test)"); ax.set_ylim(-10, 105)
    ax.text(0.01, 0.97, "mũi tên xanh: lớp cần được đánh dấu", transform=ax.transAxes, fontsize=8, color=GREEN, va="top")
    ax.legend(fontsize=8, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.2))
    fig.tight_layout(); fig.savefig(FIG / "sf_flagged.png", bbox_inches="tight"); plt.close(fig)
    # 4. ảnh mẫu có chú thích
    sys.path.insert(0, str(Path(__file__).parent))
    import sf_analyze as sa
    test = sa.load("test")
    kp, km = a["rules"]["phone"]["best_k"], a["rules"]["drink"]["best_k"]
    picks = []
    for cls in ("c0", "c2", "c4", "c6", "c9", "c5"):
        for r in test:
            f = sa.profile_features(r)
            if r["cls"] == cls and f and f[0] is not None and "pose" in r:
                picks.append(r); break
    dds = _find_dds(ROOT) / "data" / "raw" / "statefarm" / "imgs" / "train"
    fig, axes = plt.subplots(2, 3, figsize=(6.4, 3.7))
    for ax, r in zip(axes.ravel(), picks):
        img = cv2.imread(str(dds / r["cls"] / r["file"]))
        p = r["pose"]; f = sa.profile_features(r)
        ear = max((p["ear_l"], p["ear_r"]), key=lambda q: q[2])
        mouth = ((p["mouth_l"][0] + p["mouth_r"][0]) / 2, (p["mouth_l"][1] + p["mouth_r"][1]) / 2)
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        for h in sa.hand_centers(p):
            ax.plot(*h, "o", color="#FFD400", ms=7, mec="black")
        ax.plot(ear[0], ear[1], "s", color="#00E5FF", ms=6, mec="black"); ax.plot(*mouth, "^", color="#FF2D95", ms=6, mec="black")
        ax.plot(*p["nose"][:2], "x", color="white", ms=6)
        flag = []
        if f[0] is not None and f[0] < kp: flag.append("tai")
        if f[1] is not None and f[1] < km: flag.append("miệng")
        ax.set_title(f"{r['cls']}  d_tai={f[0]:.2f}  d_miệng={f[1]:.2f}\n→ " + (", ".join(flag) if flag else "không đánh dấu"),
                     fontsize=7.5, color=RED if flag else GREEN)
        ax.axis("off")
    fig.tight_layout(); fig.savefig(FIG / "sf_samples.png", bbox_inches="tight"); plt.close(fig)


GROUPS = {"ear": fig_ear, "arch": fig_arch, "fsm": fig_fsm, "budget": fig_budget, "closure": fig_closure, "signals": fig_signals,
          "osd": fig_osd, "bench": fig_bench, "sf": fig_sf}

if __name__ == "__main__":
    for name in (sys.argv[1:] or GROUPS):
        print("→", name)
        GROUPS[name]()
