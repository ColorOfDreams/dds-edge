"""Summarise a driver-level cross-validation: mean and standard deviation over the fold runs.

Looks for runs/<prefix>*/metrics.json (one run per fold, e.g. effl0_cv0 ... effl0_cv4, written by
`train.py --cv_folds 5 --cv_fold i --name effl0_cv<i>`).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True, help="run-name prefix, e.g. effl0_cv")
    ap.add_argument("--runs_dir", default="runs")
    ap.add_argument("--out", default="", help="optional markdown file to write")
    a = ap.parse_args()

    rows = []
    for mpath in sorted(Path(a.runs_dir).glob(f"{a.prefix}*/metrics.json")):
        m = json.loads(mpath.read_text())
        a_ = m["args"]
        row = {"run": mpath.parent.name, "fold": a_.get("cv_fold"), "test_drivers": len((m.get("split_groups") or {}).get("test", [])),
               "val_macro_f1": m["best_val_macro_f1"], "test_acc": m["test_acc"], "test_macro_f1": m["test_macro_f1"]}
        row.update({f"f1_{k}": v for k, v in m["test_f1_per_class"].items()})
        rows.append(row)
    if not rows:
        raise SystemExit(f"no {a.prefix}*/metrics.json under {a.runs_dir}")
    df = pd.DataFrame(rows).sort_values("fold")
    print(df.round(4).to_string(index=False))

    num = df.drop(columns=["run", "fold", "test_drivers"])
    summ = pd.DataFrame({"mean": num.mean(), "std": num.std(ddof=1) if len(df) > 1 else np.nan,
                         "min": num.min(), "max": num.max()}).round(4)
    print(f"\n{len(df)} folds: mean and sample std")
    print(summ.to_string())
    if a.out:
        Path(a.out).write_text(df.round(4).to_markdown(index=False) + "\n\n" + summ.to_markdown() + "\n")
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
