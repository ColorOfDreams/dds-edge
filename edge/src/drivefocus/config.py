"""Cấu hình: đọc YAML mặc định, cho phép ghi đè từng phần.

Cấu hình được giữ dưới dạng dict lồng nhau và bọc bằng `Cfg` để truy cập kiểu
`cfg.eyes.closed_s`. Cách này giữ file YAML là nguồn sự thật duy nhất.
"""
from __future__ import annotations

import copy
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


class Cfg:
    """Bọc dict lồng nhau để truy cập bằng thuộc tính (chỉ đọc theo quy ước)."""

    def __init__(self, data: dict[str, Any]):
        object.__setattr__(self, "_d", data)

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._d[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return Cfg(value) if isinstance(value, dict) else value

    def __getitem__(self, name: str) -> Any:
        return self.__getattr__(name)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._d)


def _merge(base: dict[str, Any], override: dict[str, Any], path: str = "") -> dict[str, Any]:
    for key, value in override.items():
        if key not in base:
            raise KeyError(f"khóa cấu hình không tồn tại: {path}{key}")
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise TypeError(f"{path}{key} phải là dict")
            _merge(base[key], value, f"{path}{key}.")
        else:
            base[key] = value
    return base


def default_dict() -> dict[str, Any]:
    text = resources.files("drivefocus").joinpath("default_config.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def load_config(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> Cfg:
    data = default_dict()
    if path:
        with open(path, encoding="utf-8") as handle:
            _merge(data, yaml.safe_load(handle) or {})
    if overrides:
        _merge(data, overrides)
    return Cfg(data)


def quick_demo_overrides() -> dict[str, Any]:
    """Rút ngắn hiệu chỉnh để thử trên bàn (webcam, không có xe thật)."""
    return {
        "eyes": {"calibration_s": 8.0, "perclos_window_s": 20.0},
        "head": {"neutral_min_s": 6.0, "neutral_min_speed_kmh": 0.0},
    }
