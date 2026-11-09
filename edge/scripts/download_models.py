"""Tải mô hình MediaPipe (Apache-2.0) vào edge/models/. Chạy: python scripts/download_models.py"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://storage.googleapis.com/mediapipe-models"
FILES = {
    "face_landmarker.task": f"{BASE}/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "hand_landmarker.task": f"{BASE}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
}


def main() -> int:
    dest = Path(__file__).resolve().parents[1] / "models"
    dest.mkdir(exist_ok=True)
    for name, url in FILES.items():
        target = dest / name
        if target.exists() and target.stat().st_size > 1_000_000:
            print(f"đã có {target}")
            continue
        print(f"tải {url}")
        urllib.request.urlretrieve(url, target)
        print(f"  -> {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
