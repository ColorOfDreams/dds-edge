# DDS-Edge: Deep Learning part (State Farm)

## Setup
```
pip install -r requirements.txt && pip install -e .
```
Download State Farm Distracted Driver Detection from Kaggle (accept the competition rules, note the license/terms for the report) and unzip so that `data/raw/statefarm/driver_imgs_list.csv` and `data/raw/statefarm/imgs/train/c0..c9` exist.

## 1) Split by driver (no subject leakage)
```
python -m dds_edge.dl.prepare_data --root data/raw/statefarm
```

## 2) Experiments (each run writes runs/<name>/metrics.json, report.txt, confusion_matrix.csv)
```
# main model
python -m dds_edge.dl.train --root data/raw/statefarm --arch mobilenet_v3_small --grouping grouped6 --name mnv3_pre_aug
# transfer learning vs scratch
python -m dds_edge.dl.train --root data/raw/statefarm --arch mobilenet_v3_small --grouping grouped6 --no-pretrained --epochs 20 --name mnv3_scratch_aug
# augmentation ablation
python -m dds_edge.dl.train --root data/raw/statefarm --arch mobilenet_v3_small --grouping grouped6 --no-aug --name mnv3_pre_noaug
# resolution ablation
python -m dds_edge.dl.train --root data/raw/statefarm --arch mobilenet_v3_small --grouping grouped6 --img_size 160 --name mnv3_pre_160
# architecture comparison
python -m dds_edge.dl.train --root data/raw/statefarm --arch efficientnet_lite0 --grouping grouped6 --name effl0_pre_aug
python -m dds_edge.dl.train --root data/raw/statefarm --arch resnet18 --grouping grouped6 --name resnet18_pre_aug
# class-grouping ablation
python -m dds_edge.dl.train --root data/raw/statefarm --arch mobilenet_v3_small --grouping full10 --name mnv3_full10
```

## 3) ONNX + INT8 PTQ + CPU latency proxy
```
python -m dds_edge.dl.export_quantize --root data/raw/statefarm --run mnv3_pre_aug --threads 1
```
Results in `runs/<name>/quant_results.json` (accuracy, macro-F1, size MB, latency median/p95 for FP32 vs INT8).
If INT8 drops macro-F1 by more than ~2 points, try `efficientnet_lite0`, more calibration images (`--calib 500`), or quantization-aware training.

## Notes for the report
- Split is by driver (subject), not by image. Report this explicitly.
- No horizontal-flip augmentation on purpose: it swaps left/right-hand classes.
- Latency is a CPU proxy via onnxruntime, not an edge-device measurement. Say so.
- Dataset limits: daytime, fixed passenger-side view, US vehicles, no IR; this is a domain gap vs. in-vehicle cameras.
- Fix the seed (`--seed`) and record library versions (`pip freeze`) for reproducibility.
