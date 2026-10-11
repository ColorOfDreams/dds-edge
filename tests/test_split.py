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
