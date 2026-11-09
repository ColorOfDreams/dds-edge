"""Trích đặc trưng DriveFocus (EAR, MAR, tư thế, tay–mặt) trên ảnh State Farm của dds-edge.

Dùng đúng giao thức chia theo tài xế của dds-edge (data/processed/manifest.csv): tập val để chọn
ngưỡng, tập test để báo cáo. Ghi kết quả ra JSON Lines để phân tích lại mà không chạy lại MediaPipe.

    python sf_extract.py --split val
    python sf_extract.py --split test
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]            # drivefocus/
def _find_dds(root):
    """dds-edge nằm cạnh drivefocus/ (bản làm việc) hoặc chính là thư mục cha (nhánh drive-focus của repo dds-edge)."""
    for cand in (root.parent / "dds-edge", root.parent):
        if (cand / "src" / "dds_edge").is_dir():
            return cand
    return root.parent / "dds-edge"


DDS = _find_dds(ROOT) / "data"
OUT = ROOT / "report" / "results"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["train", "val", "test"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from drivefocus.config import load_config
    from drivefocus.perception import MediaPipeSensor

    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    models = ROOT / "edge" / "models"
    sensor = MediaPipeSensor(load_config(), models, image_mode=True)
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(models / "pose_landmarker_full.task")),
        running_mode=vision.RunningMode.IMAGE, num_poses=1,
        min_pose_detection_confidence=0.2, min_pose_presence_confidence=0.2))   # 0,5 chỉ tìm thấy ~63% ảnh nhìn nghiêng
    # nose, mắt T/P, tai T/P, miệng T/P, vai T/P, cổ tay, ngón trỏ, ngón út, ngón cái (trái rồi phải)
    KEEP = {"nose": 0, "eye_l": 2, "eye_r": 5, "ear_l": 7, "ear_r": 8, "mouth_l": 9, "mouth_r": 10,
            "sh_l": 11, "sh_r": 12, "wr_l": 15, "wr_r": 16, "pk_l": 17, "pk_r": 18, "ix_l": 19, "ix_r": 20,
            "th_l": 21, "th_r": 22}
    rows = [r for r in csv.DictReader(open(DDS / "processed" / "manifest.csv", encoding="utf-8"))
            if r["split"] == args.split]
    if args.limit:
        rows = rows[:args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"sf_{args.split}.jsonl"
    t0 = time.time()
    missing = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            path = DDS / r["path"]
            img = cv2.imread(str(path))
            if img is None:
                missing += 1
                continue
            obs, _ = sensor.process(img, 0.0)
            pres = pose.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            d = obs.to_dict()
            if pres.pose_landmarks:
                lm = pres.pose_landmarks[0]
                d["pose"] = {k: [round(lm[i].x * img.shape[1], 1), round(lm[i].y * img.shape[0], 1),
                                 round(lm[i].visibility, 3)] for k, i in KEEP.items()}
            d.pop("t", None)
            d.update(cls=r["raw_label"], driver=r["group"], file=path.name, h=img.shape[0], w=img.shape[1])
            f.write(json.dumps(d) + "\n")
            if (i + 1) % 250 == 0:
                print(f"{args.split}: {i + 1}/{len(rows)} ({(i + 1) / (time.time() - t0):.1f} ảnh/s)", flush=True)
    print(f"xong {args.split}: {len(rows) - missing} ảnh, thiếu {missing}, {time.time() - t0:.0f}s -> {out_path}")
    sensor.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
