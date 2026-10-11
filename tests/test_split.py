import subprocess
import sys

import pandas as pd

COLUMNS = ["path", "label", "split", "group", "source", "raw_label"]


def make_statefarm(root):
    rows = [(f"p{s:03d}", f"c{c}", f"img_{s}_{c}_{k}.jpg")
            for s in range(20) for c in range(10) for k in range(3)]
    d = root / "raw" / "statefarm"
    d.mkdir(parents=True)
    pd.DataFrame(rows, columns=["subject", "classname", "img"]).to_csv(
        d / "driver_imgs_list.csv", index=False)


def run_prepare(root, *extra):
    subprocess.run([sys.executable, "-m", "dds_edge.dl.prepare_data",
                    "--data_dir", str(root), "--no_check_files", *extra], check=True)
    return pd.read_csv(root / "processed" / "manifest.csv")


def test_manifest_has_no_group_leakage(tmp_path):
    make_statefarm(tmp_path)
    m = run_prepare(tmp_path)
    assert list(m.columns) == COLUMNS
    assert set(m["split"]) == {"train", "val", "test"}
    assert (m.groupby("group")["split"].nunique() == 1).all()
    assert set(m["source"]) == {"statefarm"}
    assert m["path"].iloc[0].startswith("raw/statefarm/imgs/train/")


def test_label_follows_grouping(tmp_path):
    make_statefarm(tmp_path)
    m = run_prepare(tmp_path, "--grouping", "grouped6")
    assert set(m.loc[m["raw_label"].isin(["c1", "c2", "c3", "c4"]), "label"]) == {"phone"}
    assert set(m.loc[m["raw_label"] == "c0", "label"]) == {"normal"}
    m10 = run_prepare(tmp_path, "--grouping", "full10")
    assert (m10["label"] == m10["raw_label"]).all()


def test_preprocess_removes_duplicates_and_resizes(tmp_path):
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(0)
    rows, n = [], 0
    for g, split in [("p001", "train"), ("p002", "val")]:
        d = tmp_path / "raw" / "statefarm" / "imgs" / "train" / "c0"
        d.mkdir(parents=True, exist_ok=True)
        base = rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)
        for k in range(4):  # k=0,1 identical frames, k=2,3 distinct images
            arr = base if k < 2 else rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)
            n += 1
            name = f"img_{n}.jpg"
            Image.fromarray(arr).save(d / name, quality=100)
            rows.append((f"raw/statefarm/imgs/train/c0/{name}", "normal", split, g, "statefarm", "c0"))
    (tmp_path / "processed").mkdir()
    pd.DataFrame(rows, columns=COLUMNS).to_csv(tmp_path / "processed" / "manifest.csv", index=False)

    subprocess.run([sys.executable, "-m", "dds_edge.dl.preprocess", "--data_dir", str(tmp_path),
                    "--size", "32x24", "--workers", "1", "--out_dir", "processed/small"], check=True)

    out = pd.read_csv(tmp_path / "processed" / "small" / "manifest.csv")
    assert list(out.columns) == COLUMNS
    assert len(out) == 6  # one duplicate dropped in each of the two groups
    assert (out.groupby("group")["split"].nunique() == 1).all()
    for p in out["path"]:
        assert Image.open(tmp_path / p).size == (32, 24)
    assert len(pd.read_csv(tmp_path / "processed" / "small" / "dedup_removed.csv")) == 2
