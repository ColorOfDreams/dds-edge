"""Build the training manifest (data/processed/manifest.csv) from raw datasets.

Columns: path, label, split, group, source, raw_label   (see docs/manifest.md)

Currently supported source: State Farm Distracted Driver, expected under <data_dir>/<statefarm_dir>:
    driver_imgs_list.csv        (columns: subject, classname, img)
    imgs/train/c0/img_*.jpg ... imgs/train/c9/...
The Kaggle 'test' folder has no labels, so 'train' is split by driver (group = subject).
"""
import argparse
import random
from pathlib import Path

import pandas as pd

from dds_edge.dl.common import GROUPINGS, MANIFEST_COLUMNS, class_names

SPLITS = {"train", "val", "test"}


def scan_statefarm(data_dir: Path, sf_dir: str, img_dir: str) -> pd.DataFrame:
    lst = pd.read_csv(data_dir / sf_dir / "driver_imgs_list.csv")
    return pd.DataFrame({
        "path": f"{sf_dir}/{img_dir}/" + lst["classname"] + "/" + lst["img"],
        "group": lst["subject"],
        "source": "statefarm",
        "raw_label": lst["classname"],
    })


def assign_splits(df: pd.DataFrame, val_frac: float, test_frac: float, seed: int) -> pd.Series:
    """Split by group (not by image): every group lands in exactly one split."""
    groups = sorted(df["group"].unique())
    random.Random(seed).shuffle(groups)
    n_test = max(1, round(len(groups) * test_frac))
    n_val = max(1, round(len(groups) * val_frac))
    test_g = set(groups[:n_test])
    val_g = set(groups[n_test:n_test + n_val])
    return df["group"].map(lambda g: "test" if g in test_g else ("val" if g in val_g else "train"))


def validate(df: pd.DataFrame, grouping: str, data_dir: Path | None):
    assert set(df["split"]) <= SPLITS, f"bad split values: {set(df['split']) - SPLITS}"
    assert set(df["label"]) <= set(class_names(grouping)), "label outside grouping"
    assert not df["path"].duplicated().any(), "duplicate paths"
    assert (df.groupby("group")["split"].nunique() == 1).all(), "group leakage across splits"
    for s in ("train", "val"):
        absent = set(class_names(grouping)) - set(df.loc[df["split"] == s, "label"])
        assert not absent, f"classes missing from {s}: {sorted(absent)}"
    if data_dir is not None:
        missing = [p for p in df["path"].sample(min(200, len(df)), random_state=0)
                   if not (data_dir / p).exists()]
        assert not missing, f"missing files, e.g. {missing[:3]} (check --img_dir)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="data", help="folder that manifest paths are relative to")
    ap.add_argument("--statefarm_dir", default="raw/statefarm", help="relative to --data_dir")
    ap.add_argument("--img_dir", default="imgs/train", help="relative to --statefarm_dir")
    ap.add_argument("--grouping", default="grouped6", choices=sorted(GROUPINGS))
    ap.add_argument("--val_frac", type=float, default=0.15)
    ap.add_argument("--test_frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="processed/manifest.csv", help="relative to --data_dir")
    ap.add_argument("--no_check_files", action="store_true")
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    df = scan_statefarm(data_dir, a.statefarm_dir, a.img_dir)
    df["label"] = df["raw_label"].map(GROUPINGS[a.grouping])
    assert df["label"].notna().all(), "raw_label without mapping"
    df["split"] = assign_splits(df, a.val_frac, a.test_frac, a.seed)
    validate(df, a.grouping, None if a.no_check_files else data_dir)

    out = data_dir / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    df[MANIFEST_COLUMNS].to_csv(out, index=False)
    per = df.groupby("split")["group"].nunique()
    print(f"groups -> " + ", ".join(f"{s} {per.get(s, 0)}" for s in ("train", "val", "test")))
    print(df.groupby(["split", "label"]).size().unstack(fill_value=0))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
