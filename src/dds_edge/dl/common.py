"""Shared helpers: class groupings, transforms, dataset, model factory."""
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import Dataset
from torchvision import models
from torchvision import transforms as T

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

# State Farm classes:
# c0 safe driving, c1 texting-right, c2 phone-right, c3 texting-left, c4 phone-left,
# c5 operating radio, c6 drinking, c7 reaching behind, c8 hair/makeup, c9 talking to passenger
GROUPINGS = {
    "full10": {f"c{i}": f"c{i}" for i in range(10)},
    "grouped6": {
        "c0": "normal",
        "c1": "phone", "c2": "phone", "c3": "phone", "c4": "phone",
        "c5": "device_ops",
        "c6": "eat_drink",
        "c7": "reach_grooming", "c8": "reach_grooming",
        "c9": "talk_passenger",
    },
    "grouped5": {
        "c0": "normal",
        "c1": "phone", "c2": "phone", "c3": "phone", "c4": "phone",
        "c5": "reach_other", "c7": "reach_other", "c8": "reach_other",
        "c6": "eat_drink",
        "c9": "talk_passenger",
    },
}


def class_names(grouping: str):
    names = []
    for c in sorted(GROUPINGS[grouping]):
        n = GROUPINGS[grouping][c]
        if n not in names:
            names.append(n)
    return names


def parse_size(v) -> tuple:
    """Model input size as (height, width). Accepts 224 / "224" (square), "WxH" such as
    "320x240" (width x height, same convention as preprocess --size) or a (height, width) pair."""
    if isinstance(v, (tuple, list)):
        return int(v[0]), int(v[1])
    s = str(v).lower()
    if "x" in s:
        w, h = s.split("x")
        return int(h), int(w)
    return int(s), int(s)


def build_transform(img_size, train: bool, aug: bool, aug_level: int = 1):
    """img_size: see parse_size. aug_level 1 = baseline augmentation, 2 = stronger (wider crop/rotation/color, blur, random erasing).

    NOTE: no horizontal flip on purpose. Flipping swaps left/right-hand classes
    (c1<->c3, c2<->c4) and would corrupt labels in the full10 setting.
    """
    size = parse_size(img_size)
    base = size[1] / size[0]  # crops keep the aspect ratio of the model input
    if train and aug and aug_level >= 2:
        return T.Compose([
            T.RandomResizedCrop(size, scale=(0.6, 1.0), ratio=(0.85 * base, 1.2 * base)),
            T.RandomRotation(12),
            T.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3, hue=0.05),
            T.RandomApply([T.GaussianBlur(3, sigma=(0.1, 1.5))], p=0.2),
            T.ToTensor(),
            T.Normalize(MEAN, STD),
            T.RandomErasing(p=0.3, scale=(0.02, 0.15), value=0),
        ])
    if train and aug:
        return T.Compose([
            T.RandomResizedCrop(size, scale=(0.8, 1.0), ratio=(0.9 * base, 1.1 * base)),
            T.RandomRotation(8),
            T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
            T.ToTensor(),
            T.Normalize(MEAN, STD),
        ])
    return T.Compose([
        T.Resize(size),
        T.ToTensor(),
        T.Normalize(MEAN, STD),
    ])


MANIFEST_COLUMNS = ["path", "label", "split", "group", "source", "raw_label"]


def load_manifest(csv_path, grouping: str) -> pd.DataFrame:
    """Read the manifest. If every raw_label is known to `grouping` (State Farm c0..c9) the `label`
    column is rebuilt from it, so the class grouping can be changed at train time without
    regenerating the manifest; otherwise every label must already belong to `grouping`."""
    df = pd.read_csv(csv_path)
    missing = [c for c in MANIFEST_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path}: missing columns {missing}")
    mapping = GROUPINGS[grouping]
    if set(df["raw_label"]) <= set(mapping):
        df["label"] = df["raw_label"].map(mapping)
    unknown = sorted(set(df["label"]) - set(class_names(grouping)))
    if unknown:
        raise ValueError(f"{csv_path}: labels {unknown} not in grouping '{grouping}'; "
                         f"regenerate with prepare_data --grouping {grouping}")
    return df


def coarse_map(fine: str, coarse: str):
    """For a model trained on grouping `fine` but evaluated on grouping `coarse` (e.g. full10 -> grouped6):
    returns (fine_names, coarse_names, M) where M[i, j] = 1 if fine class i belongs to coarse class j.
    Probabilities of the fine classes are summed into the coarse classes with `probs @ M`."""
    fine_names, coarse_names = class_names(fine), class_names(coarse)
    M = np.zeros((len(fine_names), len(coarse_names)), dtype=np.float32)
    for raw, f in GROUPINGS[fine].items():
        c = GROUPINGS[coarse][raw]
        i, j = fine_names.index(f), coarse_names.index(c)
        assert M[i].sum() == 0 or M[i, j] == 1, f"'{f}' maps to several '{coarse}' classes: not a refinement"
        M[i, j] = 1
    return fine_names, coarse_names, M


def cv_group_split(groups, n_folds: int, fold: int, seed: int = 42, val_frac: float = 0.18) -> dict:
    """Driver-level K-fold: group -> 'train' | 'val' | 'test'. Fold `fold` is the test set, a seeded
    subset of the remaining drivers is val, the rest is train. Every driver is test in exactly one fold."""
    import random
    groups = sorted(set(groups))
    random.Random(seed).shuffle(groups)
    folds = [groups[i::n_folds] for i in range(n_folds)]
    test = set(folds[fold])
    rest = [g for g in groups if g not in test]
    random.Random(seed + 1 + fold).shuffle(rest)
    n_val = max(1, round(len(rest) * val_frac))
    val = set(rest[:n_val])
    return {g: ("test" if g in test else "val" if g in val else "train") for g in groups}


class SplitDataset(Dataset):
    """Images of one split. `root` is the data/ folder that manifest paths are relative to."""

    def __init__(self, root, manifest_csv, split, grouping, transform, group_split=None):
        df = load_manifest(manifest_csv, grouping)
        if group_split is not None:  # cross-validation: override the manifest split by driver group
            df = df.assign(split=df["group"].map(group_split))
        df = df[df["split"] == split].reset_index(drop=True)
        self.root = Path(root)
        self.paths = df["path"].tolist()
        self.sources = df["source"].tolist()
        self.groups = df["group"].tolist()
        names = class_names(grouping)
        self.labels = [names.index(c) for c in df["label"]]
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        img = Image.open(self.root / self.paths[i]).convert("RGB")
        return self.transform(img), self.labels[i]


def build_model(arch: str, num_classes: int, pretrained: bool):
    if arch == "mobilenet_v3_small":
        w = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        m = models.mobilenet_v3_small(weights=w)
        m.classifier[3] = nn.Linear(m.classifier[3].in_features, num_classes)
    elif arch == "resnet18":
        w = models.ResNet18_Weights.DEFAULT if pretrained else None
        m = models.resnet18(weights=w)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
    elif arch == "resnet50":
        w = models.ResNet50_Weights.DEFAULT if pretrained else None
        m = models.resnet50(weights=w)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
    elif arch == "vgg16":
        w = models.VGG16_Weights.DEFAULT if pretrained else None
        m = models.vgg16(weights=w)
        m.classifier[6] = nn.Linear(m.classifier[6].in_features, num_classes)
    elif arch == "efficientnet_lite0":
        import timm  # optional dependency
        m = timm.create_model("efficientnet_lite0", pretrained=pretrained, num_classes=num_classes)
    else:
        raise ValueError(f"unknown arch: {arch}")
    return m


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def count_macs(model: nn.Module, img_size) -> int:
    """Multiply-accumulates for one 3 x H x W image (conv + linear layers only); img_size: see parse_size."""
    from torch.utils.flop_counter import FlopCounterMode
    was_training = model.training
    model.eval()
    p = next(model.parameters())
    h, w = parse_size(img_size)
    x = torch.zeros(1, 3, h, w, device=p.device)
    with torch.no_grad(), FlopCounterMode(display=False) as fc:
        model(x)
    model.train(was_training)
    return fc.get_total_flops() // 2
