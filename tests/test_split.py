import subprocess
import sys

import pandas as pd


def test_split_has_no_subject_leakage(tmp_path):
    rows = [(f"p{s:03d}", f"c{c}", f"img_{s}_{c}_{k}.jpg")
            for s in range(20) for c in range(10) for k in range(3)]
    pd.DataFrame(rows, columns=["subject", "classname", "img"]).to_csv(
        tmp_path / "driver_imgs_list.csv", index=False)

    subprocess.run([sys.executable, "-m", "dds_edge.dl.prepare_data",
                    "--root", str(tmp_path), "--no_check_files"], check=True)

    s = pd.read_csv(tmp_path / "splits.csv")
    assert set(s["split"]) == {"train", "val", "test"}
    assert (s.groupby("subject")["split"].nunique() == 1).all()
