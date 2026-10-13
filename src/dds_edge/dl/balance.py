"""Balance the TRAIN split of a manifest at the data level. Val and test are never touched.

    python -m dds_edge.dl.balance --mode cap  --target 2000    # undersample big classes
    python -m dds_edge.dl.balance --mode aug  --target 2000    # oversample small classes with saved augmented copies
    python -m dds_edge.dl.balance --mode both --target 2000    # both: every class ends at about `target`

Classes are the manifest `label` (the 6 behaviour groups) or `--by raw_label` (the 10 original classes).

* cap  : keeps at most `target` train images per class, taken round-robin over the drivers, so every
         driver stays represented (random inside a driver, fixed seed).
* aug  : adds new images to classes below `target`. Each one is an augmented copy (random crop, small
         rotation, brightness/contrast/colour change; never a horizontal flip) of a real train image of that
         class, saved as a JPEG under <dataset>/images/aug/ and added to the manifest with the same driver.
* both : cap, then aug.
Output: manifest_<mode>.csv next to the input manifest (paths relative to --data_dir, like the original).
"""
import argparse
import random
from pathlib import Path

import pandas as pd
from PIL import Image
from torchvision import transforms as T

from dds_edge.dl.common import MANIFEST_COLUMNS


def cap_class(rows: pd.DataFrame, target: int, rng: random.Random) -> pd.DataFrame:
    """At most `target` rows, round-robin over drivers (group) so no driver disappears."""
    if len(rows) <= target:
        return rows
    per = {g: list(d.index) for g, d in rows.groupby("group")}
    for idx in per.values():
        rng.shuffle(idx)
    order = list(per)
    rng.shuffle(order)
    keep = []
    while len(keep) < target and any(per.values()):
        for g in order:
            if per[g] and len(keep) < target:
                keep.append(per[g].pop())
    return rows.loc[keep]


def augment_pipeline():
    return T.Compose([
        T.RandomResizedCrop((240, 320), scale=(0.7, 1.0), ratio=(1.2, 1.45)),  # keeps the 4:3 shape
        T.RandomRotation(8),
        T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.03),
    ])


def make_aug_rows(rows: pd.DataFrame, need: int, data_dir: Path, out_dir: str, rng: random.Random) -> list:
    """Create `need` augmented copies of images in `rows` (cycling through them in random order)."""
    import torch
    torch.manual_seed(rng.randrange(1 << 30))  # torchvision draws its random parameters from torch
    pipe = augment_pipeline()
    src = list(rows.index)
    rng.shuffle(src)
    new = []
    for k in range(need):
        r = rows.loc[src[k % len(src)]]
        copy_no = k // len(src) + 1
        stem = Path(r["path"]).stem
        rel = f"{out_dir}/{r['raw_label']}/{stem}_aug{copy_no}.jpg"
        dst = data_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(data_dir / r["path"]) as im:
            pipe(im.convert("RGB")).save(dst, "JPEG", quality=90)
        row = r.copy()
        row["path"] = rel
        new.append(row)
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["cap", "aug", "both"])
    ap.add_argument("--target", type=int, required=True, help="images per class in train")
    ap.add_argument("--by", default="label", choices=["label", "raw_label"])
    ap.add_argument("--data_dir", default="data")
    ap.add_argument("--manifest", default="processed/sf_320x240/manifest.csv", help="relative to --data_dir")
    ap.add_argument("--aug_dir", default="processed/sf_320x240/images/aug", help="relative to --data_dir")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    src_path = data_dir / a.manifest
    df = pd.read_csv(src_path)
    rng = random.Random(a.seed)
    train = df[df["split"] == "train"]
    rest = df[df["split"] != "train"]  # val and test: untouched

    parts = []
    for cls, rows in train.groupby(a.by):
        if a.mode in ("cap", "both"):
            rows = cap_class(rows, a.target, rng)
        parts.append(rows)
        if a.mode in ("aug", "both") and len(rows) < a.target:
            parts.append(pd.DataFrame(make_aug_rows(rows, a.target - len(rows), data_dir,
                                                    f"{a.aug_dir}/{a.mode}", rng)))
    new_train = pd.concat(parts, ignore_index=True)
    out = pd.concat([new_train, rest], ignore_index=True)

    assert out.loc[out["split"] != "train"].reset_index(drop=True).equals(rest.reset_index(drop=True)), "val/test changed"
    assert not out["path"].duplicated().any(), "duplicate paths"
    assert (out.groupby("group")["split"].nunique() == 1).all(), "driver split broken"

    out_path = src_path.with_name(f"manifest_{a.mode}.csv")
    out[MANIFEST_COLUMNS].to_csv(out_path, index=False)
    before = train[a.by].value_counts()
    after = new_train[a.by].value_counts()
    print(f"train images per {a.by}  (before -> after)")
    for c in sorted(before.index):
        print(f"  {c:16s}{before[c]:6d} -> {after.get(c, 0):6d}")
    print(f"train total {len(train)} -> {len(new_train)};  val/test unchanged ({len(rest)} images)")
    print(f"max/min ratio {before.max() / before.min():.2f} -> {after.max() / after.min():.2f}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
