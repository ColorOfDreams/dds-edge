"""Train and evaluate a lightweight classifier for driver distraction."""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader

from dds_edge.dl.common import (SplitDataset, build_model, build_transform, class_names,
                    count_params)


def set_seed(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    torch.cuda.manual_seed_all(s)


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    ys, ps = [], []
    for x, y in loader:
        out = model(x.to(device))
        ps.extend(out.argmax(1).cpu().tolist())
        ys.extend(y.tolist())
    return np.array(ys), np.array(ps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data", help="data/ folder that manifest paths are relative to")
    ap.add_argument("--manifest", default="processed/manifest.csv", help="relative to --root")
    ap.add_argument("--arch", default="mobilenet_v3_small",
                    choices=["mobilenet_v3_small", "resnet18", "efficientnet_lite0"])
    ap.add_argument("--grouping", default="grouped6", choices=["full10", "grouped6", "grouped5"])
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
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
                          build_transform(a.img_size, s == "train", a.aug))
          for s in ["train", "val", "test"]}
    dl = {s: DataLoader(ds[s], batch_size=a.batch_size, shuffle=(s == "train"),
                        num_workers=a.workers, pin_memory=True)
          for s in ds}

    model = build_model(a.arch, len(names), a.pretrained).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
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
            x, y = x.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                loss = criterion(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            loss_sum += loss.item() * len(y)
            n += len(y)
        sched.step()

        yv, pv = predict(model, dl["val"], device)
        f1 = f1_score(yv, pv, average="macro")
        acc = accuracy_score(yv, pv)
        history.append({"epoch": ep, "train_loss": loss_sum / n, "val_acc": acc,
                        "val_macro_f1": f1, "sec": time.time() - t0})
        print(f"ep {ep:02d} loss {loss_sum / n:.4f} val_acc {acc:.4f} val_f1 {f1:.4f}")
        if f1 > best_f1:
            best_f1 = f1
            torch.save({"state_dict": model.state_dict(), "arch": a.arch,
                        "img_size": a.img_size, "grouping": a.grouping,
                        "class_names": names}, out / "best.pt")

    # final test on best checkpoint
    ck = torch.load(out / "best.pt", map_location=device)
    model.load_state_dict(ck["state_dict"])
    yt, pt = predict(model, dl["test"], device)
    labels = list(range(len(names)))
    metrics = {
        "args": vars(a),
        "n_params": count_params(model),
        "best_val_macro_f1": best_f1,
        "test_acc": accuracy_score(yt, pt),
        "test_macro_f1": f1_score(yt, pt, average="macro"),
        "test_f1_per_class": dict(zip(names, f1_score(yt, pt, average=None, labels=labels).tolist())),
    }
    np.savetxt(out / "confusion_matrix.csv", confusion_matrix(yt, pt, labels=labels),
               fmt="%d", delimiter=",", header=",".join(names), comments="")
    (out / "report.txt").write_text(
        classification_report(yt, pt, labels=labels, target_names=names, digits=4))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "history.json").write_text(json.dumps(history, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if k != "args"}, indent=2))


if __name__ == "__main__":
    main()
