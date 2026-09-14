"""
tools/schema.py — 素材定義 schema 與資源清單
=============================================
提供統一的「素材定義 → dict → JSON」序列化，以及 AssetManifest
（記錄所有產生素材的清單，供工具鏈/manifest.json 使用）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """遞迴轉為可 JSON 序列化結構（處理 dataclass / tuple / set）。"""
    from dataclasses import is_dataclass

    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(to_jsonable(v) for v in obj)
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def write_json(path: str, data: Any, indent: int = 2) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(data), f, ensure_ascii=False, indent=indent)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(slots=True)
class AssetManifest:
    """產生素材清單：asset 型別 → 檔案路徑清單。"""

    generated_at: str = "pipeline"
    assets: dict[str, list[str]] = field(default_factory=dict)

    def add(self, category: str, path: str) -> None:
        self.assets.setdefault(category, []).append(path)

    def to_dict(self) -> dict:
        return {"generated_at": self.generated_at, "assets": self.assets}
