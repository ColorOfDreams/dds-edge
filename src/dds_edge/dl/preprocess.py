"""Clean and resize the dataset, then write a self-contained package (images + manifest).

1. Near-duplicate removal: frames cut from the same video are almost identical. Inside each
   (source, group, raw_label) cell, images are visited in file-name order and one is dropped
   when it is closer than --dedup_thresh to an image already kept (mean absolute pixel
   difference of 32x24 grayscale thumbnails; 0 = identical, ~2 = barely different frames).
2. Resize every kept image to one size (default 320x240, keeps the 4:3 ratio of the originals).

Output (all under <data_dir>/<out_dir>, default processed/sf_320x240):
    images/<source>/<raw_label>/<file>.jpg
    manifest.csv          same columns as the input manifest, `path` relative to <data_dir>
    dedup_removed.csv     removed image -> the kept image it duplicates, with the distance

On Kaggle, upload that folder as a dataset and link it back to data/processed/sf_320x240.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from dds_edge.dl.common import MANIFEST_COLUMNS
from dds_edge.dl.prepare_data import report_balance

THUMB = (32, 24)


def _thumb(path):
    with Image.open(path) as im:
        im.draft("L", (THUMB[0] * 5, THUMB[1] * 5))  # fast JPEG decode at reduced size
        return np.asarray(im.convert("L").resize(THUMB), dtype=np.float32).ravel()


def _resize(job):
    src, dst, size, quality = job
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.convert("RGB").resize(size, Image.LANCZOS).save(dst, "JPEG", quality=quality)


def find_duplicates(df: pd.DataFrame, thumbs: np.ndarray, thresh: float):
    """Return (kept mask, list of (removed_index, kept_index, distance))."""
    keep = np.ones(len(df), dtype=bool)
    removed = []
    order = df["path"].str.extract(r"(\d+)")[0].astype("int64")  # numeric id ~ frame order
    for _, cell in df.assign(_o=order).sort_values("_o").groupby(
            ["source", "group", "raw_label"], sort=False):
        kept = []
        for i in cell.index:
            if kept:
                d = np.abs(thumbs[kept] - thumbs[i]).mean(axis=1)
                j = int(d.argmin())
                if d[j] < thresh:
                    keep[i] = False
                    removed.append((i, kept[j], float(d[j])))
                    continue
            kept.append(i)
    return keep, removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="data", help="folder that manifest paths are relative to")
    ap.add_argument("--manifest", default="processed/manifest.csv", help="relative to --data_dir")
    ap.add_argument("--out_dir", default="processed/sf_320x240", help="relative to --data_dir")
    ap.add_argument("--size", default="320x240", help="WIDTHxHEIGHT of the saved images")
    ap.add_argument("--quality", type=int, default=90, help="JPEG quality")
    ap.add_argument("--dedup_thresh", type=float, default=2.0,
                    help="drop images closer than this to a kept one; 0 disables")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    w, h = (int(v) for v in a.size.lower().split("x"))
    df = pd.read_csv(data_dir / a.manifest)
    n0 = len(df)

    removed_rows = []
    if a.dedup_thresh > 0:
        with ProcessPoolExecutor(a.workers) as ex:
            thumbs = np.stack(list(ex.map(_thumb, [data_dir / p for p in df["path"]], chunksize=64)))
        keep, removed = find_duplicates(df, thumbs, a.dedup_thresh)
        removed_rows = [{"removed": df.at[i, "path"], "kept": df.at[j, "path"],
                         "split": df.at[i, "split"], "distance": round(d, 3)}
                        for i, j, d in removed]
        df = df[keep].reset_index(drop=True)
    print(f"dedup (thresh {a.dedup_thresh}): {n0} -> {len(df)} images "
          f"({n0 - len(df)} removed, {(n0 - len(df)) / n0:.1%})")

    out_dir = data_dir / a.out_dir
    names = df["path"].map(lambda p: Path(p).name)
    new_rel = ("images/" + df["source"] + "/" + df["raw_label"] + "/" + names).tolist()
    jobs = [(str(data_dir / s), str(out_dir / r), (w, h), a.quality)
            for s, r in zip(df["path"], new_rel)]
    with ProcessPoolExecutor(a.workers) as ex:
        list(ex.map(_resize, jobs, chunksize=64))

    df["path"] = [f"{a.out_dir}/{r}" for r in new_rel]
    assert (df.groupby("group")["split"].nunique() == 1).all(), "group leakage across splits"
    assert not df["path"].duplicated().any(), "duplicate paths"
    assert all((data_dir / p).exists() for p in df["path"].sample(min(200, len(df)), random_state=0))
    df[MANIFEST_COLUMNS].to_csv(out_dir / "manifest.csv", index=False)
    pd.DataFrame(removed_rows, columns=["removed", "kept", "split", "distance"]).to_csv(
        out_dir / "dedup_removed.csv", index=False)

    print("\nremoved per split:")
    if removed_rows:
        print(pd.DataFrame(removed_rows).groupby("split").size().to_string())
    report_balance(df)
    size_mb = sum(f.stat().st_size for f in (out_dir / "images").rglob("*.jpg")) / 1e6
    print(f"\n{len(df)} images {w}x{h}, {size_mb:.0f} MB -> {out_dir}")


if __name__ == "__main__":
    main()
