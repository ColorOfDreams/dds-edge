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
