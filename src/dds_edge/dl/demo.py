"""Demo: run the INT8 ONNX model on images and show label, confidence and latency per image.

    python -m dds_edge.dl.demo --run effl0_clean --runs_dir drive/dds-edge-runs/dds-edge-runs
    python -m dds_edge.dl.demo --run effl0_clean --runs_dir ... --images some.jpg other.jpg

Without --images it takes random test images from the manifest (the true label is shown too) and
saves a picture grid to <run>/demo.jpg.
"""
import argparse
import random
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import torch
from PIL import Image, ImageDraw, ImageFont

from dds_edge.dl.common import build_transform, parse_size


def load_font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--runs_dir", default="runs")
    ap.add_argument("--model", default="model_int8.onnx", help="ONNX file inside the run folder")
    ap.add_argument("--root", default="data")
    ap.add_argument("--manifest", default="processed/sf_320x240/manifest.csv")
    ap.add_argument("--images", nargs="*", help="image files; default: random test images from the manifest")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--threads", type=int, default=1)
    a = ap.parse_args()

    run = Path(a.runs_dir) / a.run
    ck = torch.load(run / "best.pt", map_location="cpu")
    names, size = ck["class_names"], parse_size(ck["img_size"])
    tf = build_transform(ck["img_size"], train=False, aug=False)
    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    sess = ort.InferenceSession(str(run / a.model), so, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name

    items = []  # (path, true label or None)
    if a.images:
        items = [(Path(p), None) for p in a.images]
    else:
        df = pd.read_csv(Path(a.root) / a.manifest)
        df = df[df["split"] == "test"]
        picks = random.Random(a.seed).sample(range(len(df)), a.n)
        items = [(Path(a.root) / df.iloc[i]["path"], df.iloc[i]["label"]) for i in picks]

    x0 = tf(Image.open(items[0][0]).convert("RGB")).numpy()[None].astype(np.float32)
    for _ in range(5):  # warm up
        sess.run(None, {inp: x0})

    tiles, correct, times = [], 0, []
    print(f"model {a.model}  input {size[1]}x{size[0]}  classes {names}\n")
    print(f"{'image':28s}{'true':16s}{'predicted':16s}{'conf':>6s}{'ms':>8s}")
    for path, true in items:
        img = Image.open(path).convert("RGB")
        x = tf(img).numpy()[None].astype(np.float32)
        t = time.perf_counter()
        logits = sess.run(None, {inp: x})[0][0]
        ms = (time.perf_counter() - t) * 1000
        p = np.exp(logits - logits.max())
        p /= p.sum()
        k = int(p.argmax())
        times.append(ms)
        ok = true is None or names[k] == true
        correct += ok and true is not None
        print(f"{path.name:28s}{(true or '-'):16s}{names[k]:16s}{p[k]:6.2f}{ms:8.2f}")
        tile = img.resize((320, 240))
        d = ImageDraw.Draw(tile)
        col = (0, 200, 90) if ok else (235, 60, 80)
        d.rectangle((0, 0, 320, 54), fill=(0, 0, 0))
        d.text((6, 4), f"{names[k]}  {p[k]:.0%}", fill=col, font=load_font(20))
        d.text((6, 30), (f"thật: {true}  " if true else "") + f"{ms:.1f} ms", fill=(255, 255, 255), font=load_font(15))
        d.rectangle((0, 0, 319, 239), outline=col, width=4)
        tiles.append(tile)

    labelled = [t for _, t in items if t]
    if labelled:
        print(f"\ncorrect {correct}/{len(labelled)}")
    print(f"latency median {np.median(times):.2f} ms  ->  {1000 / np.median(times):.0f} FPS (CPU, {a.threads} thread)")

    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    grid = Image.new("RGB", (cols * 320, rows * 240), (255, 255, 255))
    for i, t in enumerate(tiles):
        grid.paste(t, ((i % cols) * 320, (i // cols) * 240))
    out = run / "demo.jpg"
    grid.save(out, quality=90)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
