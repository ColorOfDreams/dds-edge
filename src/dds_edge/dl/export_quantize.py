"""Export a trained checkpoint to ONNX, quantize to INT8 (post-training), and compare float vs INT8.

Reports accuracy, macro-F1, model size, CPU latency / FPS (batch 1) and throughput (batch 16)
for both models. Latency here is a CPU proxy (onnxruntime, limited threads), NOT a measurement
on an edge device.

Quantization options (all post-training, no retraining):
  --quant static    weights AND activations -> INT8, activation ranges measured on --calib train images
  --quant dynamic   weights -> INT8, activations quantized on the fly (no calibration; often little
                    speed-up for convolutional nets on CPU)
  --calib_method    how static activation ranges are chosen: minmax | entropy | percentile
  --quant_format    qdq (Quantize/Dequantize nodes) | qoperator (fused quantized operators)
  --per_channel     one scale per output channel for weights (usually more accurate)
Use --tag to keep several variants of the same run side by side.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import (CalibrationDataReader, CalibrationMethod, QuantFormat,
                                      QuantType, quantize_dynamic, quantize_static)
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score

from dds_edge.dl.common import (build_model, build_transform, class_names, count_macs, count_params,
                                load_manifest)


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
    b16 = np.stack(arrays[:16]) if len(arrays) >= 16 else np.repeat(one, 16, axis=0)
    sess.run(None, {name: b16})
    t = time.perf_counter()
    for _ in range(10):
        sess.run(None, {name: b16})
    throughput = 10 * len(b16) / (time.perf_counter() - t)
    return {
        "acc": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
        "size_mb": Path(path).stat().st_size / 1e6,
        "latency_ms_median": float(np.median(times)),
        "fps_median": float(1000 / np.median(times)),
        "latency_ms_p95": float(np.percentile(times, 95)),
        "throughput_img_s_batch16": float(throughput),
    }


def quantize(src, dst, a, calib):
    if a.quant == "dynamic":
        quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8)
        return
    method = {"minmax": CalibrationMethod.MinMax, "entropy": CalibrationMethod.Entropy,
              "percentile": CalibrationMethod.Percentile}[a.calib_method]
    fmt = QuantFormat.QDQ if a.quant_format == "qdq" else QuantFormat.QOperator
    quantize_static(str(src), str(dst), Reader(calib, "input"), quant_format=fmt,
                    per_channel=a.per_channel, weight_type=QuantType.QInt8,
                    activation_type=QuantType.QUInt8, calibrate_method=method)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data", help="data/ folder that manifest paths are relative to")
    ap.add_argument("--manifest", default="processed/manifest.csv", help="relative to --root")
    ap.add_argument("--run", required=True, help="run name under runs/")
    ap.add_argument("--calib", type=int, default=200, help="train images used to calibrate (static)")
    ap.add_argument("--quant", default="static", choices=["static", "dynamic"])
    ap.add_argument("--calib_method", default="minmax", choices=["minmax", "entropy", "percentile"])
    ap.add_argument("--quant_format", default="qdq", choices=["qdq", "qoperator"])
    ap.add_argument("--per_channel", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--tag", default="", help="suffix for the output files, e.g. entropy")
    ap.add_argument("--threads", type=int, default=1)
    a = ap.parse_args()

    out = Path("runs") / a.run
    if not (out / "best.pt").exists():
        raise SystemExit(f"{out / 'best.pt'} not found: download/copy the checkpoint of run '{a.run}' first")
    ck = torch.load(out / "best.pt", map_location="cpu")
    names, img_size, grouping = ck["class_names"], ck["img_size"], ck["grouping"]
    model = build_model(ck["arch"], len(names), pretrained=False)
    model.load_state_dict(ck["state_dict"])

    sfx = f"_{a.tag}" if a.tag else ""
    fp32, int8 = out / "model_fp32.onnx", out / f"model_int8{sfx}.onnx"
    export_onnx(model, img_size, fp32)

    df = load_manifest(Path(a.root) / a.manifest, grouping)
    tf = build_transform(img_size, train=False, aug=False)
    calib = []
    if a.quant == "static":
        train = df[df["split"] == "train"]
        calib_paths = train.sample(min(a.calib, len(train)), random_state=0)["path"]
        calib = [load_array(a.root, p, tf) for p in calib_paths]
    try:
        from onnxruntime.quantization.shape_inference import quant_pre_process
        pre = out / "model_fp32_pre.onnx"
        quant_pre_process(str(fp32), str(pre))
        src = pre
    except Exception:
        src = fp32
    quantize(src, int8, a, calib)

    test = df[df["split"] == "test"]
    labels = [names.index(c) for c in test["label"]]
    arrays = [load_array(a.root, p, tf) for p in test["path"]]

    res = {"n_params": count_params(model), "macs": count_macs(model, img_size),
           "fp32": evaluate(fp32, arrays, labels, a.threads),
           "int8": evaluate(int8, arrays, labels, a.threads),
           "quant_config": {"quant": a.quant, "calib_method": a.calib_method if a.quant == "static" else None,
                            "quant_format": a.quant_format if a.quant == "static" else None,
                            "per_channel": a.per_channel if a.quant == "static" else None,
                            "calib_images": len(calib), "tag": a.tag},
           "threads": a.threads, "note": "CPU proxy, not an edge device"}
    (out / f"quant_results{sfx}.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
