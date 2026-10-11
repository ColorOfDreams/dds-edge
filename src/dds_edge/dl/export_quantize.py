"""Export a trained checkpoint to ONNX, apply static INT8 PTQ, and compare float vs INT8.

Reports accuracy, macro-F1, model size and CPU latency (batch 1) for both models.
Latency here is a CPU proxy (onnxruntime, limited threads), NOT a measurement on an edge device.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import torch
from onnxruntime.quantization import (CalibrationDataReader, QuantFormat, QuantType,
                                      quantize_static)
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score

from dds_edge.dl.common import GROUPINGS, build_model, build_transform, class_names


def export_onnx(model, img_size, path):
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size)
    kwargs = dict(input_names=["input"], output_names=["logits"], opset_version=13,
                  dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}})
    try:
        torch.onnx.export(model, dummy, str(path), dynamo=False, **kwargs)
    except TypeError:  # older torch without the dynamo argument
        torch.onnx.export(model, dummy, str(path), **kwargs)


class Reader(CalibrationDataReader):
    def __init__(self, arrays, name):
        self.it = iter([{name: a[None]} for a in arrays])

    def get_next(self):
        return next(self.it, None)


def load_array(root, rel, tf):
    return tf(Image.open(Path(root) / rel).convert("RGB")).numpy().astype(np.float32)


def evaluate(path, arrays, labels, threads):
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    preds = []
    for i in range(0, len(arrays), 32):
        batch = np.stack(arrays[i:i + 32])
        preds.extend(sess.run(None, {name: batch})[0].argmax(1).tolist())
    one = arrays[0][None]
    for _ in range(10):
        sess.run(None, {name: one})
    times = []
    for _ in range(100):
        t = time.perf_counter()
        sess.run(None, {name: one})
        times.append((time.perf_counter() - t) * 1000)
    return {
        "acc": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
        "size_mb": Path(path).stat().st_size / 1e6,
        "latency_ms_median": float(np.median(times)),
        "latency_ms_p95": float(np.percentile(times, 95)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--splits", default="splits.csv")
    ap.add_argument("--run", required=True, help="run name under runs/")
    ap.add_argument("--calib", type=int, default=200)
    ap.add_argument("--threads", type=int, default=1)
    a = ap.parse_args()

    out = Path("runs") / a.run
    ck = torch.load(out / "best.pt", map_location="cpu")
    names, img_size, grouping = ck["class_names"], ck["img_size"], ck["grouping"]
    model = build_model(ck["arch"], len(names), pretrained=False)
    model.load_state_dict(ck["state_dict"])

    fp32, int8 = out / "model_fp32.onnx", out / "model_int8.onnx"
    export_onnx(model, img_size, fp32)

    df = pd.read_csv(Path(a.root) / a.splits)
    tf = build_transform(img_size, train=False, aug=False)
    calib_paths = df[df["split"] == "train"].sample(a.calib, random_state=0)["path"]
    calib = [load_array(a.root, p, tf) for p in calib_paths]
    try:
        from onnxruntime.quantization.shape_inference import quant_pre_process
        pre = out / "model_fp32_pre.onnx"
        quant_pre_process(str(fp32), str(pre))
        src = pre
    except Exception:
        src = fp32
    quantize_static(str(src), str(int8), Reader(calib, "input"),
                    quant_format=QuantFormat.QDQ, per_channel=True,
                    weight_type=QuantType.QInt8, activation_type=QuantType.QUInt8)

    test = df[df["split"] == "test"]
    mapping = GROUPINGS[grouping]
    labels = [class_names(grouping).index(mapping[c]) for c in test["classname"]]
    arrays = [load_array(a.root, p, tf) for p in test["path"]]

    res = {"fp32": evaluate(fp32, arrays, labels, a.threads),
           "int8": evaluate(int8, arrays, labels, a.threads),
           "threads": a.threads, "note": "CPU proxy, not an edge device"}
    (out / "quant_results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
