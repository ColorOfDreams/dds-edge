"""Train and evaluate a lightweight classifier for driver distraction."""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader

from dds_edge.dl.common import (SplitDataset, build_model, build_transform, class_names,
                    count_macs, count_params, parse_size)


def set_seed(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    torch.cuda.manual_seed_all(s)


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    ys, ps, probs = [], [], []
    for x, y in loader:
        out = model(x.to(device, non_blocking=True, memory_format=torch.channels_last))
        probs.append(out.float().softmax(1).cpu().numpy())
        ps.extend(out.argmax(1).cpu().tolist())
        ys.extend(y.tolist())
    return np.array(ys), np.array(ps), np.concatenate(probs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data", help="data/ folder that manifest paths are relative to")
    ap.add_argument("--manifest", default="processed/manifest.csv", help="relative to --root")
    ap.add_argument("--arch", default="mobilenet_v3_small",
                    choices=["mobilenet_v3_small", "resnet18", "resnet50", "vgg16", "efficientnet_lite0"])
    ap.add_argument("--grouping", default="grouped6", choices=["full10", "grouped6", "grouped5"])
    ap.add_argument("--img_size", default="224",
                    help="model input: 224 (square) or WIDTHxHEIGHT such as 320x240 (native, keeps 4:3)")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight_decay", type=float, default=1e-4)
    ap.add_argument("--label_smoothing", type=float, default=0.1)
    ap.add_argument("--class_weight", default="none", choices=["none", "sqrt", "inverse"],
                    help="weight the loss per class from train counts: sqrt = inverse^0.5")
    ap.add_argument("--sampler", default="none", choices=["none", "sqrt", "balanced"],
                    help="oversample small classes each epoch: sqrt = freq^-0.5, balanced = freq^-1")
    ap.add_argument("--aug_level", type=int, default=1, choices=[1, 2],
                    help="1 = baseline augmentation, 2 = stronger (see build_transform)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--aug", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()

    set_seed(a.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    names = class_names(a.grouping)
    manifest = Path(a.root) / a.manifest

    ds = {s: SplitDataset(a.root, manifest, s, a.grouping,
                          build_transform(a.img_size, s == "train", a.aug, a.aug_level))
          for s in ["train", "val", "test"]}
    cuda = device.type == "cuda"
    torch.backends.cudnn.benchmark = cuda  # autotune conv kernels for fixed-size inputs
    loader_kw = dict(num_workers=a.workers, pin_memory=cuda)
    if a.workers > 0:  # keep workers alive between epochs and prefetch batches
        loader_kw.update(persistent_workers=True, prefetch_factor=4)
    sampler = None
    if a.sampler != "none":  # draw samples with probability ~ class_frequency^-power (with replacement)
        cnt = np.bincount(ds["train"].labels, minlength=len(names))
        sw = (1.0 / cnt) ** (1.0 if a.sampler == "balanced" else 0.5)
        sampler = torch.utils.data.WeightedRandomSampler(
            torch.as_tensor(sw[ds["train"].labels], dtype=torch.double), len(ds["train"]), replacement=True)
    dl = {s: DataLoader(ds[s], batch_size=a.batch_size * (1 if s == "train" else 2),
                        shuffle=(s == "train" and sampler is None),
                        sampler=sampler if s == "train" else None,
                        drop_last=(s == "train"), **loader_kw)
          for s in ds}

    model = build_model(a.arch, len(names), a.pretrained).to(
        device, memory_format=torch.channels_last)
    weight = None
    if a.class_weight != "none":
        counts = np.bincount(ds["train"].labels, minlength=len(names))
        w = (counts.sum() / (len(names) * counts)) ** (1.0 if a.class_weight == "inverse" else 0.5)
        weight = torch.tensor(w / w.mean(), dtype=torch.float32, device=device)
        print("class weights:", dict(zip(names, weight.cpu().numpy().round(3).tolist())))
    criterion = nn.CrossEntropyLoss(weight=weight, label_smoothing=a.label_smoothing)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=a.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    out = Path("runs") / a.name
    out.mkdir(parents=True, exist_ok=True)
    best_f1, history = -1.0, []

    for ep in range(1, a.epochs + 1):
        model.train()
        t0, loss_sum, n = time.time(), 0.0, 0
        for x, y in dl["train"]:
            x = x.to(device, non_blocking=True, memory_format=torch.channels_last)
            y = y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                loss = criterion(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            loss_sum += loss.item() * len(y)
            n += len(y)
        sched.step()

        yv, pv, _ = predict(model, dl["val"], device)
        f1 = f1_score(yv, pv, average="macro")
        acc = accuracy_score(yv, pv)
        history.append({"epoch": ep, "train_loss": loss_sum / n, "val_acc": acc,
                        "val_macro_f1": f1, "sec": time.time() - t0})
        print(f"ep {ep:02d} loss {loss_sum / n:.4f} val_acc {acc:.4f} val_f1 {f1:.4f}", flush=True)
        if f1 > best_f1:
            best_f1 = f1
            torch.save({"state_dict": model.state_dict(), "arch": a.arch,
                        "img_size": list(parse_size(a.img_size)), "grouping": a.grouping,
                        "class_names": names}, out / "best.pt")

    # final test on best checkpoint
    ck = torch.load(out / "best.pt", map_location=device)
    model.load_state_dict(ck["state_dict"])
    yt, pt, prob = predict(model, dl["test"], device)
    labels = list(range(len(names)))
    metrics = {
        "args": vars(a),
        "n_params": count_params(model),
        "macs": count_macs(model, a.img_size),
        "best_val_macro_f1": best_f1,
        "test_acc": accuracy_score(yt, pt),
        "test_macro_f1": f1_score(yt, pt, average="macro"),
        "test_f1_per_class": dict(zip(names, f1_score(yt, pt, average=None, labels=labels).tolist())),
    }
    pred_df = pd.DataFrame({"path": ds["test"].paths, "group": ds["test"].groups,
                            "source": ds["test"].sources, "true": [names[i] for i in yt],
                            "pred": [names[i] for i in pt]})
    for k, nme in enumerate(names):
        pred_df[f"p_{nme}"] = prob[:, k].round(4)
    pred_df.to_csv(out / "predictions.csv", index=False)  # per-image test predictions, see analyze.py
    np.savetxt(out / "confusion_matrix.csv", confusion_matrix(yt, pt, labels=labels),
               fmt="%d", delimiter=",", header=",".join(names), comments="")
    (out / "report.txt").write_text(
        classification_report(yt, pt, labels=labels, target_names=names, digits=4))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "history.json").write_text(json.dumps(history, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if k != "args"}, indent=2))


if __name__ == "__main__":
    main()
