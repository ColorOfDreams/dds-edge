# DDS-Edge

Driver distraction detection on edge AI. Three course tracks share one repo:

| Track | Folder | Status |
|---|---|---|
| Deep Learning (train, quantize) | `src/dds_edge/dl` | in progress |
| Computer Vision (preprocessing, video, edge inference) | `src/dds_edge/cv` (create when started) | planned |
| Big Data (FleetStream: GPS stream, aggregation, API) | `src/dds_edge/stream`, `src/dds_edge/api` | planned |

## Setup
```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
pytest
```

## Layout
```
src/dds_edge/    code (one subpackage per track)
tests/           pytest
data/raw/        downloaded datasets (git-ignored), e.g. data/raw/statefarm
data/own_recordings/   self-recorded clips (git-ignored, consent + privacy)
configs/         experiment configs
scripts/         one-off helpers
notebooks/       exploration
reports/         LaTeX report
docs/            notes (docs/dl.md = DL commands)
runs/            training outputs (git-ignored)
```

Deep Learning commands: see `docs/dl.md`.
