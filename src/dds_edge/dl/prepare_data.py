"""Create a subject-disjoint train/val/test split for State Farm Distracted Driver.

Expected layout under --root (as downloaded from Kaggle):
    driver_imgs_list.csv        (columns: subject, classname, img)
    imgs/train/c0/img_*.jpg ... imgs/train/c9/...
The Kaggle 'test' folder has no labels, so we split 'train' by driver (subject).
"""
import argparse
import random
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--img_dir", default="imgs/train")
    ap.add_argument("--val_frac", type=float, default=0.15)
    ap.add_argument("--test_frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="splits.csv")
    ap.add_argument("--no_check_files", action="store_true")
    a = ap.parse_args()

    root = Path(a.root)
    df = pd.read_csv(root / "driver_imgs_list.csv")
    df["path"] = a.img_dir + "/" + df["classname"] + "/" + df["img"]

    subjects = sorted(df["subject"].unique())
    rng = random.Random(a.seed)
    rng.shuffle(subjects)
    n = len(subjects)
    n_test = max(1, round(n * a.test_frac))
    n_val = max(1, round(n * a.val_frac))
    test_s = set(subjects[:n_test])
    val_s = set(subjects[n_test:n_test + n_val])

    def which(s):
        return "test" if s in test_s else ("val" if s in val_s else "train")

    df["split"] = df["subject"].map(which)

    # leakage check: no subject in more than one split
    per_subject = df.groupby("subject")["split"].nunique()
    assert (per_subject == 1).all(), "subject leakage across splits"

    if not a.no_check_files:
        missing = [p for p in df["path"].sample(min(200, len(df)), random_state=0)
                   if not (root / p).exists()]
        assert not missing, f"missing files, e.g. {missing[:3]} (check --img_dir)"

    df[["path", "subject", "classname", "split"]].to_csv(root / a.out, index=False)
    print(f"{n} subjects -> train {n - n_test - n_val}, val {n_val}, test {n_test}")
    print(df.groupby(["split", "classname"]).size().unstack(fill_value=0))
    print(f"wrote {root / a.out}")


if __name__ == "__main__":
    main()
