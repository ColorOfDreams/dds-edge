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


def _tiny_dataset(tmp_path, n_per=6):
    """6 classes x 2 groups per split of tiny random images + a manifest (paths relative to tmp_path)."""
    import numpy as np
    from PIL import Image

    names = ["normal", "phone", "device_ops", "eat_drink", "reach_grooming", "talk_passenger"]
    rng = np.random.default_rng(0)
    rows, k = [], 0
    (tmp_path / "img").mkdir()
    for split, groups in [("train", ["p1", "p2"]), ("val", ["p3"]), ("test", ["p4", "p5"])]:
        for g in groups:
            for c, name in enumerate(names):
                for _ in range(n_per):
                    k += 1
                    Image.fromarray(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)).save(
                        tmp_path / "img" / f"{k}.jpg")
                    rows.append((f"img/{k}.jpg", name, split, g, "statefarm", f"c{c}"))
    pd.DataFrame(rows, columns=COLUMNS).to_csv(tmp_path / "manifest.csv", index=False)


def test_train_analyze_summarize_pipeline(tmp_path, monkeypatch):
    _tiny_dataset(tmp_path)
    monkeypatch.chdir(tmp_path)
    for extra in (["--aug_level", "2", "--sampler", "balanced", "--class_weight", "sqrt"], []):
        subprocess.run([sys.executable, "-m", "dds_edge.dl.train", "--root", str(tmp_path),
                        "--manifest", "manifest.csv", "--epochs", "1", "--workers", "0",
                        "--img_size", "64", "--batch_size", "8", "--no-pretrained",
                        "--name", "t_" + ("strong" if extra else "base"), *extra], check=True)
    pred = pd.read_csv(tmp_path / "runs" / "t_strong" / "predictions.csv")
    assert {"path", "group", "true", "pred", "p_normal", "p_talk_passenger"} <= set(pred.columns)
    assert len(pred) == 2 * 6 * 6  # 2 test groups x 6 classes x 6 images
    assert set(pred["group"]) == {"p4", "p5"}

    subprocess.run([sys.executable, "-m", "dds_edge.dl.analyze", "--run", "t_strong",
                    "--data_dir", str(tmp_path), "--montage", "normal", "phone"], check=True)
    subprocess.run([sys.executable, "-m", "dds_edge.dl.summarize", "--out_dir", "rep"], check=True)
    summary = pd.read_csv(tmp_path / "rep" / "summary.csv")
    assert set(summary["run"]) == {"t_strong", "t_base"}
    assert summary.loc[summary["run"] == "t_strong", "sampler"].iloc[0] == "balanced"
