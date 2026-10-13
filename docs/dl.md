# DDS-Edge: Deep Learning part (State Farm)

## Setup
```
pip install -r requirements.txt && pip install -e .
```
Download State Farm Distracted Driver Detection from Kaggle (accept the competition rules, note the license/terms for the report) and unzip so that `data/raw/statefarm/driver_imgs_list.csv` and `data/raw/statefarm/imgs/train/c0..c9` exist. Each dataset gets its own folder under `data/raw/`.

## 1) Build the manifest (split by driver, no leakage)
```
python -m dds_edge.dl.prepare_data
```
Writes `data/processed/manifest.csv` (columns `path,label,split,group,source,raw_label`, see `docs/manifest.md`). Image paths are relative to `data/`; `--root` of train/export defaults to `data`.
`label` is fixed when the manifest is built (default `--grouping grouped6`). For the 10-class ablation build its own manifest:
```
python -m dds_edge.dl.prepare_data --grouping full10 --out processed/manifest_full10.csv
```

## 2) Experiments (each run writes runs/<name>/metrics.json, report.txt, confusion_matrix.csv)
```
# main model
python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --name mnv3_pre_aug
# transfer learning vs scratch
python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --no-pretrained --epochs 20 --name mnv3_scratch_aug
# augmentation ablation
python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --no-aug --name mnv3_pre_noaug
# resolution ablation
python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping grouped6 --img_size 160 --name mnv3_pre_160
# architecture comparison
python -m dds_edge.dl.train --arch efficientnet_lite0 --grouping grouped6 --name effl0_pre_aug
python -m dds_edge.dl.train --arch resnet18 --grouping grouped6 --name resnet18_pre_aug
# class-grouping ablation
python -m dds_edge.dl.train --arch mobilenet_v3_small --grouping full10 --manifest processed/manifest_full10.csv --name mnv3_full10
```

## 3) ONNX + INT8 PTQ + CPU latency proxy
```
python -m dds_edge.dl.export_quantize --run mnv3_pre_aug --threads 1
```
Results in `runs/<name>/quant_results.json` (accuracy, macro-F1, size MB, latency median/p95 for FP32 vs INT8).
If INT8 drops macro-F1 by more than ~2 points, try `efficientnet_lite0`, more calibration images (`--calib 500`), or quantization-aware training.

## Notes for the report
- Split is by driver (subject), not by image. Report this explicitly.
- No horizontal-flip augmentation on purpose: it swaps left/right-hand classes.
- Latency is a CPU proxy via onnxruntime, not an edge-device measurement. Say so.
- Dataset limits: daytime, fixed passenger-side view, US vehicles, no IR; this is a domain gap vs. in-vehicle cameras.
- Fix the seed (`--seed`) and record library versions (`pip freeze`) for reproducibility.

## 4) Error analysis, improvements, quantization variants, summary
```
# per-image test predictions are written by train.py to runs/<name>/predictions.csv
python -m dds_edge.dl.analyze --run mnv3_clean                       # confusion matrix, per class, per driver
python -m dds_edge.dl.analyze --run mnv3_clean --montage talk_passenger normal   # look at the mistakes

# imbalance / augmentation (one change per run)
python -m dds_edge.dl.train ... --class_weight sqrt            # or inverse
python -m dds_edge.dl.train ... --sampler sqrt                 # or balanced (oversample small classes)
python -m dds_edge.dl.train ... --aug_level 2                  # stronger augmentation
python -m dds_edge.dl.train ... --img_size 320x240              # input size: 224 (square) or WIDTHxHEIGHT, keeps 4:3

# quantization variants of one run (--tag keeps the files apart)
python -m dds_edge.dl.export_quantize --run mnv3_clean --calib_method entropy --tag entropy
python -m dds_edge.dl.export_quantize --run mnv3_clean --quant dynamic --tag dyn

# one table + plot over all runs: reports/summary.csv, summary.md, summary_plot.png
python -m dds_edge.dl.summarize
```
The notebooks `notebooks/colab_train.ipynb` (Vietnamese, step by step) and `notebooks/kaggle_train.ipynb` run these on a GPU.

## 5) Local web demo

The browser demo uses a saved PyTorch checkpoint directly (no extra web-framework dependency):

```
python -m dds_edge.dl.web_demo --run effl0_clean --runs-dir dds-edge-runs
```

Open `http://127.0.0.1:8000`, upload or drag a JPG/PNG/WebP cabin frame, or select **Mở camera trực tiếp** and grant the browser camera permission. Camera mode samples a frame about every 0.9 seconds. Review the predicted group, confidence, top-3 scores, and CPU inference time. The server is local and processes uploads/camera frames in memory only.

## 5) Data-level class balancing (train split only; val/test untouched)
```
python -m dds_edge.dl.balance --mode cap  --target 2000     # undersample big classes, round-robin over drivers
python -m dds_edge.dl.balance --mode aug  --target 2000     # add saved augmented copies to small classes
python -m dds_edge.dl.balance --mode both --target 2000     # every class ends at 2000
# -> processed/sf_320x240/manifest_{cap,aug,both}.csv ; train with --manifest processed/sf_320x240/manifest_cap.csv

# train on the 10 original (balanced) classes, score on the 6 groups by summing probabilities
python -m dds_edge.dl.train --grouping full10 --eval_grouping grouped6 --manifest processed/sf_320x240/manifest.csv ...
```
`load_manifest` rebuilds `label` from `raw_label`, so `--grouping` can be changed at train time without regenerating the manifest.
Notebook: `notebooks/colab_balance.ipynb` (Vietnamese, one explanation per cell).

Driver-level cross-validation: `train.py --cv_folds 5 --cv_fold i`, then `python -m dds_edge.dl.cv_summary --prefix <name>`.
Demo on a few images with the INT8 model: `python -m dds_edge.dl.demo --run <run> --runs_dir <dir>`.
