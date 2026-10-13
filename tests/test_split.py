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

    from dds_edge.dl.common import GROUPINGS

    raw = [f"c{i}" for i in range(10)]
    rng = np.random.default_rng(0)
    rows, k = [], 0
    (tmp_path / "img").mkdir()
    for split, groups in [("train", ["p1", "p2"]), ("val", ["p3"]), ("test", ["p4", "p5"])]:
        for g in groups:
            for c, rl in enumerate(raw):
                name = GROUPINGS["grouped6"][rl]
                for _ in range(n_per):
                    k += 1
                    Image.fromarray(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)).save(
                        tmp_path / "img" / f"{k}.jpg")
                    rows.append((f"img/{k}.jpg", name, split, g, "statefarm", rl))
    pd.DataFrame(rows, columns=COLUMNS).to_csv(tmp_path / "manifest.csv", index=False)


def test_train_analyze_summarize_pipeline(tmp_path, monkeypatch):
    _tiny_dataset(tmp_path)
    monkeypatch.chdir(tmp_path)
    for extra in (["--aug_level", "2", "--sampler", "balanced", "--class_weight", "sqrt"], []):
        subprocess.run([sys.executable, "-m", "dds_edge.dl.train", "--root", str(tmp_path),
                        "--manifest", "manifest.csv", "--epochs", "1", "--workers", "0",
                        "--img_size", "64x48" if extra else "64", "--batch_size", "8",
                        "--no-pretrained", "--name", "t_" + ("strong" if extra else "base"), *extra],
                       check=True)
    pred = pd.read_csv(tmp_path / "runs" / "t_strong" / "predictions.csv")
    assert {"path", "group", "true", "pred", "p_c0", "p_c9"} <= set(pred.columns)  # default: 10 classes
    assert len(pred) == 2 * 10 * 6  # 2 test groups x 10 raw classes x 6 images
    assert set(pred["group"]) == {"p4", "p5"}

    subprocess.run([sys.executable, "-m", "dds_edge.dl.analyze", "--run", "t_strong",
                    "--data_dir", str(tmp_path), "--montage", "normal", "phone"], check=True)
    subprocess.run([sys.executable, "-m", "dds_edge.dl.summarize", "--out_dir", "rep"], check=True)
    summary = pd.read_csv(tmp_path / "rep" / "summary.csv")
    assert set(summary["run"]) == {"t_strong", "t_base"}
    assert summary.loc[summary["run"] == "t_strong", "sampler"].iloc[0] == "balanced"


def test_input_size_square_and_rectangular():
    import torch
    from PIL import Image
    from dds_edge.dl.common import build_model, build_transform, count_macs, parse_size

    assert parse_size(224) == parse_size("224") == (224, 224)
    assert parse_size("320x240") == (240, 320)  # WIDTHxHEIGHT -> (height, width)
    assert parse_size([240, 320]) == (240, 320)
    img = Image.new("RGB", (320, 240))
    for size, shape in [("224", (3, 224, 224)), ("320x240", (3, 240, 320))]:
        for train, level in [(False, 1), (True, 1), (True, 2)]:
            x = build_transform(size, train, True, level)(img)
            assert tuple(x.shape) == shape
    m = build_model("mobilenet_v3_small", 6, False)
    assert count_macs(m, "320x240") > count_macs(m, 224)  # more pixels -> more MACs
    assert tuple(m(torch.zeros(1, 3, 240, 320)).shape) == (1, 6)


def test_cv_driver_folds_are_disjoint_and_cover_all_drivers():
    from dds_edge.dl.common import cv_group_split

    drivers = [f"p{i:03d}" for i in range(26)]
    tests = []
    for f in range(5):
        m = cv_group_split(drivers, 5, f)
        assert set(m) == set(drivers) and set(m.values()) == {"train", "val", "test"}
        tests.append({g for g, v in m.items() if v == "test"})
    assert sum(len(t) for t in tests) == 26 and set.union(*tests) == set(drivers)  # every driver tested once
    assert all(not (tests[i] & tests[j]) for i in range(5) for j in range(i + 1, 5))


def test_cv_training_and_summary(tmp_path, monkeypatch):
    _tiny_dataset(tmp_path)
    monkeypatch.chdir(tmp_path)
    for fold in (0, 1):
        subprocess.run([sys.executable, "-m", "dds_edge.dl.train", "--root", str(tmp_path),
                        "--manifest", "manifest.csv", "--epochs", "1", "--workers", "0", "--img_size", "64",
                        "--batch_size", "8", "--no-pretrained", "--cv_folds", "2", "--cv_fold", str(fold),
                        "--name", f"cv{fold}"], check=True)
    out = subprocess.run([sys.executable, "-m", "dds_edge.dl.cv_summary", "--prefix", "cv"],
                         check=True, capture_output=True, text=True).stdout
    assert "2 folds" in out


def test_balance_and_fine_label_training(tmp_path, monkeypatch):
    from dds_edge.dl.common import coarse_map

    _tiny_dataset(tmp_path)
    monkeypatch.chdir(tmp_path)
    for mode in ("cap", "aug", "both"):
        subprocess.run([sys.executable, "-m", "dds_edge.dl.balance", "--mode", mode, "--target", "9",
                        "--data_dir", str(tmp_path), "--manifest", "manifest.csv", "--aug_dir", "img_aug"],
                       check=True)
    orig = pd.read_csv(tmp_path / "manifest.csv")
    for mode in ("cap", "aug", "both"):
        m = pd.read_csv(tmp_path / f"manifest_{mode}.csv")
        assert (m.groupby("group")["split"].nunique() == 1).all()
        # val and test are identical to the original
        key = ["path", "label", "split", "group", "source", "raw_label"]
        for sp in ("val", "test"):
            assert m[m.split == sp][key].reset_index(drop=True).equals(orig[orig.split == sp][key].reset_index(drop=True))
        counts = m[m.split == "train"].groupby("label").size()
        if mode == "cap":
            assert counts.max() <= 9
        if mode == "both":
            assert (counts == 9).all()  # every class ends exactly at the target
    both = pd.read_csv(tmp_path / "manifest_both.csv")
    assert all((tmp_path / p).exists() for p in both["path"])

    # train on the 10 original classes, score on the 6 groups
    subprocess.run([sys.executable, "-m", "dds_edge.dl.train", "--root", str(tmp_path), "--manifest",
                    "manifest_both.csv", "--epochs", "1", "--workers", "0", "--img_size", "64", "--batch_size", "8",
                    "--no-pretrained", "--grouping", "full10", "--eval_grouping", "grouped6", "--name", "fine"],
                   check=True)
    import json
    m = json.loads((tmp_path / "runs" / "fine" / "metrics.json").read_text())
    assert set(m["test_f1_per_class"]) == {"normal", "phone", "device_ops", "eat_drink", "reach_grooming",
                                           "talk_passenger"}
    assert len(m["test_f1_per_class_fine"]) == 10
    pred = pd.read_csv(tmp_path / "runs" / "fine" / "predictions.csv")
    assert {"p_phone", "p_talk_passenger"} <= set(pred.columns) and set(pred["true"]) <= set(m["test_f1_per_class"])

    fine, coarse, M = coarse_map("full10", "grouped6")
    assert M.shape == (10, 6) and (M.sum(1) == 1).all() and M[:, coarse.index("phone")].sum() == 4
