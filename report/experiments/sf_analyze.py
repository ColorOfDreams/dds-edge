"""Phân tích kết quả State Farm: tỉ lệ tìm thấy mặt/tư thế và luật hình học tay–đầu (biến thể nhìn nghiêng).

Luật cho ảnh nhìn nghiêng dùng mô hình tư thế cơ thể của MediaPipe (tai, miệng, cổ tay, ngón tay):
    d_tai   = khoảng cách (tâm bàn tay -> tai quay về camera) / cỡ đầu
    d_miệng = khoảng cách (tâm bàn tay -> miệng) / cỡ đầu           cỡ đầu = |mũi - tai|
Ngưỡng chọn trên tập val (F1 lớn nhất), báo cáo trên tập test (khác tài xế).
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "report" / "results"

CLASS_NAME = {"c0": "lái xe an toàn", "c1": "nhắn tin, tay phải", "c2": "gọi điện, tay phải", "c3": "nhắn tin, tay trái",
              "c4": "gọi điện, tay trái", "c5": "thao tác radio", "c6": "uống nước", "c7": "với ra sau",
              "c8": "chải tóc, trang điểm", "c9": "nói chuyện với hành khách"}


def load(split):
    return [json.loads(l) for l in open(RES / f"sf_{split}.jsonl", encoding="utf-8")]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def hand_centers(p, min_vis=0.3):
    out = []
    for s in ("l", "r"):
        pts = [p[f"{k}_{s}"] for k in ("wr", "ix", "pk", "th") if p[f"{k}_{s}"][2] >= min_vis]
        if len(pts) >= 2:
            out.append((sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)))
    return out


def profile_features(r, min_vis=0.3):
    """Trả (d_tai, d_miệng, cỡ đầu) hoặc None nếu không đủ điểm."""
    p = r.get("pose")
    if not p:
        return None
    ear = max((p["ear_l"], p["ear_r"]), key=lambda q: q[2])
    nose = p["nose"]
    if ear[2] < min_vis or nose[2] < min_vis:
        return None
    head = dist(nose, ear)
    if head < 8:
        return None
    mouth = ((p["mouth_l"][0] + p["mouth_r"][0]) / 2, (p["mouth_l"][1] + p["mouth_r"][1]) / 2)
    hands = hand_centers(p)
    if not hands:
        return (None, None, head)
    return (min(dist(h, ear) for h in hands) / head, min(dist(h, mouth) for h in hands) / head, head)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def sweep(rows, idx, positives, ks):
    """Quét ngưỡng k: ảnh được gắn cờ khi d < k. Ảnh không có tư thế/không thấy tay tính là không gắn cờ."""
    out = []
    feats = [(profile_features(r), r["cls"] in positives) for r in rows]
    for k in ks:
        tp = fp = fn = 0
        for f, pos in feats:
            flag = bool(f and f[idx] is not None and f[idx] < k)
            tp += flag and pos
            fp += flag and not pos
            fn += (not flag) and pos
        p, r, f1 = prf(tp, fp, fn)
        out.append({"k": k, "precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn})
    return out


def auc(rows, idx, positives):
    """AUC của điểm số = -d (d nhỏ => nghiêng về dương). Ảnh thiếu đặc trưng bị bỏ khỏi phép tính."""
    pos, neg = [], []
    for r in rows:
        f = profile_features(r)
        if f and f[idx] is not None:
            (pos if r["cls"] in positives else neg).append(-f[idx])
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum, i = 0.0, 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(lbl for _, lbl in allv[i:j])
        i = j
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    val, test = load("val"), load("test")
    res = {"n": {"val": len(val), "test": len(test)}}

    # 1. tỉ lệ phát hiện theo lớp (tập test)
    det = defaultdict(lambda: Counter())
    for r in test:
        c = det[r["cls"]]
        c["n"] += 1
        c["face"] += bool(r["face"])
        c["eyes"] += bool(r.get("eyes_observable"))
        c["pose"] += "pose" in r
        c["feat"] += profile_features(r) is not None
    res["detection"] = {c: dict(v) for c, v in sorted(det.items())}
    tot = Counter()
    for v in det.values():
        tot.update(v)
    res["detection_total"] = dict(tot)

    # 2. quét ngưỡng trên val, đánh giá trên test
    ks = [round(0.25 + 0.25 * i, 2) for i in range(0, 48)]
    rules = {"phone": (0, {"c2", "c4"}), "drink": (1, {"c6"})}
    res["rules"] = {}
    for name, (idx, pos) in rules.items():
        sv = sweep(val, idx, pos, ks)
        best = max(sv, key=lambda x: x["f1"])
        st = sweep(test, idx, pos, [best["k"]])[0]
        res["rules"][name] = {"positives": sorted(pos), "val_sweep": sv, "best_k": best["k"], "val_best": best,
                              "test_at_best": st, "auc_val": auc(val, idx, pos), "auc_test": auc(test, idx, pos),
                              "test_sweep": sweep(test, idx, pos, ks)}

    # 3. tỉ lệ gắn cờ theo lớp trên test tại ngưỡng đã chọn
    flagged = {}
    for name, (idx, _) in rules.items():
        k = res["rules"][name]["best_k"]
        by = defaultdict(lambda: [0, 0])
        for r in test:
            f = profile_features(r)
            by[r["cls"]][1] += 1
            by[r["cls"]][0] += bool(f and f[idx] is not None and f[idx] < k)
        flagged[name] = {c: {"flagged": a, "n": b, "rate": a / b} for c, (a, b) in sorted(by.items())}
    res["flagged_by_class"] = flagged

    # 4. cả hai luật cùng lúc: "tay gần đầu" so với lái xe an toàn
    kp, km = res["rules"]["phone"]["best_k"], res["rules"]["drink"]["best_k"]
    anyflag = defaultdict(lambda: [0, 0])
    for r in test:
        f = profile_features(r)
        flag = bool(f and ((f[0] is not None and f[0] < kp) or (f[1] is not None and f[1] < km)))
        anyflag[r["cls"]][1] += 1
        anyflag[r["cls"]][0] += flag
    res["any_hand_near_head"] = {c: {"flagged": a, "n": b, "rate": a / b} for c, (a, b) in sorted(anyflag.items())}

    (RES / "sf_analysis.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    d = res["detection_total"]
    print(f"test: {d['n']} ảnh | thấy mặt {d['face']} ({d['face'] / d['n']:.1%}) | mắt quan sát được {d['eyes']} | "
          f"có tư thế {d['pose']} ({d['pose'] / d['n']:.1%}) | đủ đặc trưng {d['feat']} ({d['feat'] / d['n']:.1%})")
    for name, r in res["rules"].items():
        t = r["test_at_best"]
        print(f"{name}: k*={r['best_k']} (val F1={r['val_best']['f1']:.3f}) -> test P={t['precision']:.3f} R={t['recall']:.3f} "
              f"F1={t['f1']:.3f} | AUC val={r['auc_val']:.3f} test={r['auc_test']:.3f}")
    print("tay gần đầu theo lớp (test):", {c: round(v["rate"], 2) for c, v in res["any_hand_near_head"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
