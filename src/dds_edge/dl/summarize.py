"""Collect every run under runs/ into one comparison table (CSV + Markdown) and a plot.

Reads runs/<name>/metrics.json (written by train.py) and, when present,
runs/<name>/quant_results*.json (written by export_quantize.py). One row per run, and one extra
row per quantization variant (so FP32 and each INT8 variant can be compared on size/latency/F1).
"""
import argparse
import json
from pathlib import Path

import pandas as pd

ARG_KEYS = ["arch", "img_size", "epochs", "lr", "weight_decay", "label_smoothing", "class_weight", "sampler",
            "aug_level", "seed"]


def load_runs(runs_dir: Path) -> pd.DataFrame:
    rows = []
    for mpath in sorted(runs_dir.glob("*/metrics.json")):
        run = mpath.parent.name
        m = json.loads(mpath.read_text())
        args = m.get("args", {})
        base = {"run": run, **{k: args.get(k) for k in ARG_KEYS},
                "params_M": m["n_params"] / 1e6,
                "macs_M": m["macs"] / 1e6 if "macs" in m else None,
                "val_macro_f1": m.get("best_val_macro_f1"),
                "test_acc": m["test_acc"], "test_macro_f1": m["test_macro_f1"]}
        for cls, f1 in m.get("test_f1_per_class", {}).items():
            base[f"f1_{cls}"] = f1
        qfiles = sorted(mpath.parent.glob("quant_results*.json"))
        if not qfiles:
            rows.append({**base, "precision": "fp32"})
            continue
        for qpath in qfiles:
            q = json.loads(qpath.read_text())
            fp, i8 = q["fp32"], q["int8"]
            cfg = q.get("quant_config", {})
            rows.append({**base, "precision": "fp32", "size_mb": fp["size_mb"],
                         "latency_ms": fp["latency_ms_median"], "latency_p95_ms": fp["latency_ms_p95"],
                         "fps": fp["fps_median"], "throughput_b16": fp.get("throughput_img_s_batch16"),
                         "onnx_macro_f1": fp["macro_f1"]})
            label = "int8" + (f" ({cfg['tag']})" if cfg.get("tag") else "")
            rows.append({**base, "run": run, "precision": label, "size_mb": i8["size_mb"],
                         "latency_ms": i8["latency_ms_median"], "latency_p95_ms": i8["latency_ms_p95"],
                         "fps": i8["fps_median"], "throughput_b16": i8.get("throughput_img_s_batch16"),
                         "onnx_macro_f1": i8["macro_f1"],
                         "f1_drop_vs_fp32": fp["macro_f1"] - i8["macro_f1"]})
    df = pd.DataFrame(rows)
    return df.drop_duplicates(subset=["run", "precision"]) if len(df) else df


def make_plot(df: pd.DataFrame, path: Path, all_variants: bool = False):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: skipping the plot")
        return
    if not all_variants and "precision" in df.columns:  # default view: FP32 and the default INT8 only
        df = df[df["precision"].isin(["fp32", "int8"])]
    # y = F1 of the model that was actually measured (the INT8 point uses the INT8 model's F1)
    df = df.assign(plot_f1=df["onnx_macro_f1"].fillna(df["test_macro_f1"]) if "onnx_macro_f1" in df.columns
                   else df["test_macro_f1"])
    d = df[df["latency_ms"].notna()] if "latency_ms" in df.columns else df.iloc[0:0]
    if d.empty:
        d, x, xl = df.dropna(subset=["macs_M"]), "macs_M", "MACs (millions)"
    else:
        x, xl = "latency_ms", "CPU latency, batch 1 (ms, lower is faster)"
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for prec, g in d.groupby("precision"):
        ax.scatter(g[x], g["plot_f1"], label=prec, s=60)
        for r in g.itertuples():
            ax.annotate(r.run, (getattr(r, x), r.plot_f1), fontsize=8, xytext=(4, 4),
                        textcoords="offset points")
    ax.set_xlabel(xl)
    ax.set_ylabel("test macro-F1 of the plotted model")
    ax.grid(alpha=.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"saved plot {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs_dir", default="runs")
    ap.add_argument("--out_dir", default="reports")
    ap.add_argument("--plot_all", action="store_true", help="plot every quantization variant, not just fp32/int8")
    a = ap.parse_args()
    df = load_runs(Path(a.runs_dir))
    if df.empty:
        raise SystemExit(f"no runs/*/metrics.json under {a.runs_dir}")
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "summary.csv", index=False)
    cols = [c for c in ["run", "precision", "img_size", "params_M", "macs_M", "size_mb", "latency_ms", "fps",
                        "val_macro_f1", "test_acc", "test_macro_f1", "onnx_macro_f1", "f1_drop_vs_fp32",
                        "f1_normal", "f1_talk_passenger"] if c in df.columns]
    table = df[cols].round(4)
    (out / "summary.md").write_text(table.to_markdown(index=False) if _has_tabulate() else table.to_string(index=False))
    print(table.to_string(index=False))
    make_plot(df, out / "summary_plot.png", a.plot_all)
    print(f"wrote {out / 'summary.csv'} and {out / 'summary.md'}")


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
