"""Error analysis of one run from runs/<run>/predictions.csv (written by train.py).

Prints: confusion matrix (counts and row %), per-class precision/recall/F1, the most frequent
confusions and per-driver accuracy. With --montage TRUE PRED it also saves a picture of the
images of class TRUE that the model labelled PRED (most confident mistakes first), to look at them.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support


def top_confusions(cm: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    rows = [(t, p, int(cm.loc[t, p]), cm.loc[t, p] / cm.loc[t].sum())
            for t in cm.index for p in cm.columns if t != p and cm.loc[t, p] > 0]
    out = pd.DataFrame(rows, columns=["true", "predicted_as", "n", "share_of_true_class"])
    return out.sort_values("n", ascending=False).head(k).reset_index(drop=True)


def per_driver(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g, d in df.groupby("group"):
        rows.append({"group": g, "n": len(d), "acc": accuracy_score(d["true"], d["pred"]),
                     "macro_f1": f1_score(d["true"], d["pred"], average="macro")})
    return pd.DataFrame(rows).round(4)


def make_montage(df, data_dir, true, pred, out_path, n=12, cols=4, size=(240, 180)):
    from PIL import Image, ImageDraw
    sel = df[(df["true"] == true) & (df["pred"] == pred)].copy()
    if sel.empty:
        print(f"no image of class '{true}' predicted as '{pred}'")
        return
    sel = sel.sort_values(f"p_{pred}", ascending=False).head(n)
    rows = (len(sel) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * size[0], rows * size[1]))
    for i, r in enumerate(sel.itertuples()):
        im = Image.open(Path(data_dir) / r.path).convert("RGB").resize(size)
        ImageDraw.Draw(im).text((4, 4), f"{r.group}  p={getattr(r, 'p_' + pred):.2f}", fill=(255, 255, 0))
        canvas.paste(im, ((i % cols) * size[0], (i // cols) * size[1]))
    canvas.save(out_path, quality=88)
    print(f"saved {len(sel)} images ({true} -> {pred}) to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run name under runs/")
    ap.add_argument("--runs_dir", default="runs")
    ap.add_argument("--data_dir", default="data", help="needed only for --montage")
    ap.add_argument("--montage", nargs=2, metavar=("TRUE", "PRED"),
                    help="save images of class TRUE predicted as PRED")
    ap.add_argument("--n", type=int, default=12, help="images in the montage")
    a = ap.parse_args()

    run = Path(a.runs_dir) / a.run
    df = pd.read_csv(run / "predictions.csv")
    names = [c[2:] for c in df.columns if c.startswith("p_")]

    cm = pd.crosstab(df["true"], df["pred"]).reindex(index=names, columns=names, fill_value=0)
    pd.set_option("display.width", 200)
    print(f"== {a.run}: {len(df)} test images, acc {accuracy_score(df['true'], df['pred']):.4f}, "
          f"macro-F1 {f1_score(df['true'], df['pred'], average='macro'):.4f}")
    print("\nconfusion matrix (rows = true class, columns = predicted):")
    print(cm.to_string())
    print("\nsame, row %  (each row sums to 100):")
    print((cm.div(cm.sum(axis=1), axis=0) * 100).round(1).to_string())

    p, r, f, sup = precision_recall_fscore_support(df["true"], df["pred"], labels=names, zero_division=0)
    print("\nper class:")
    print(pd.DataFrame({"precision": p, "recall": r, "f1": f, "support": sup}, index=names).round(3).to_string())

    print("\nmost frequent confusions:")
    print(top_confusions(cm).round(3).to_string(index=False))

    print("\nper driver (test):")
    print(per_driver(df).to_string(index=False))

    if a.montage:
        make_montage(df, a.data_dir, a.montage[0], a.montage[1],
                     run / f"mis_{a.montage[0]}_as_{a.montage[1]}.jpg", a.n)


if __name__ == "__main__":
    main()
