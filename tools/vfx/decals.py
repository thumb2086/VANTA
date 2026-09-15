"""
tools/vfx/decals.py — 命中貼花（bullet hole / burn / blood …）
===========================================================
貼花 = 「尺寸 + 圖層 + 程序化形状」定義，渲染層用 Godot `Decal` 節點或
網頁展示台的貼片網格呈現；不需要任何外部圖片資產。
"""

from __future__ import annotations


def _d(name: str, **kw) -> dict:
    base = {
        "name": name,
        "size": 0.30,              # 世界坐標直徑（公尺）
        "depth": 0.05,            # 貼花厚度（Decal 法線方向）
        "color": "#1a1a1a",       # 主色（與表面混合）
        "rim": "#000000",         # 焦黑/外圈
        "opacity": 0.95,
        "shape": "hole",          # hole / burn / ring / crack / splash / mark / pixel
        "emissive": "",           # 非空 → 自發光邊框（能量類武器）
        "lifetime": 18.0,         # 秒；之後淡出回收
        "pitting": 8,             # 缺口/碎屑數量
        "seed": 0,
    }
    base.update(kw)
    return base


DECALS: dict[str, dict] = {
    "bullet_hole": _d("bullet_hole", size=0.16, color="#141210", rim="#3a3630",
                      shape="hole", pitting=10),
    "ricochet_mark": _d("ricochet_mark", size=0.22, color="#1c1a16", rim="#6a5f46",
                        shape="streak", pitting=6),
    "burn_hole": _d("burn_hole", size=0.30, color="#0b0709", rim="#2a1030",
                    shape="burn", emissive="#8b30d8", pitting=12, lifetime=10.0),
    "scorch_ring": _d("scorch_ring", size=0.34, color="#191410", rim="#4a3210",
                      shape="ring", emissive="#ffb020", lifetime=9.0),
    "holy_mark": _d("holy_mark", size=0.32, color="#dfe9f5", rim="#8fc4ff",
                    shape="mark", emissive="#bfe0ff", lifetime=8.0, opacity=0.8),
    "melt_hole": _d("melt_hole", size=0.28, color="#120705", rim="#ff5b18",
                    shape="burn", emissive="#ff7a2a", pitting=14, lifetime=12.0),
    "pixel_burn": _d("pixel_burn", size=0.26, color="#0a1018", rim="#00f5c8",
                     shape="pixel", emissive="#00ffd0", pitting=9, lifetime=6.0),
    "frost_crack": _d("frost_crack", size=0.30, color="#cfe8f7", rim="#8fd8ff",
                      shape="crack", emissive="#bfe9ff", pitting=7, lifetime=14.0),
    "acid_burn": _d("acid_burn", size=0.32, color="#14300f", rim="#4dff8a",
                    shape="burn", emissive="#8aff4d", pitting=11, lifetime=16.0),
    "stardust_dust": _d("stardust_dust", size=0.24, color="#171432", rim="#8ea0ff",
                        shape="splash", emissive="#b8c4ff", lifetime=8.0, opacity=0.7),
    "petal_mark": _d("petal_mark", size=0.22, color="#f6dfe4", rim="#e2425c",
                     shape="mark", emissive="#ff9aa8", lifetime=7.0, opacity=0.75),
    "blood_spatter": _d("blood_spatter", size=0.36, color="#6e0f12", rim="#3a0708",
                        shape="splash", pitting=16, lifetime=25.0, opacity=0.9),
    "blood_hole": _d("blood_hole", size=0.18, color="#57090c", rim="#2b0506",
                     shape="hole", pitting=6, lifetime=25.0),
    "glass_crack": _d("glass_crack", size=0.42, color="#dfefff", rim="#9fb8cc",
                      shape="crack", pitting=13, lifetime=15.0, opacity=0.65),
}

DECAL_SHAPES: tuple[str, ...] = ("hole", "streak", "burn", "ring", "crack",
                                 "splash", "mark", "pixel")


def decal_names() -> list[str]:
    return sorted(DECALS)


def resolve(name: str) -> dict:
    return DECALS.get(name or "", DECALS["bullet_hole"])


def validate_decals() -> list[str]:
    issues: list[str] = []
    for name, d in DECALS.items():
        if d["shape"] not in DECAL_SHAPES:
            issues.append(f"{name}: 未知 shape {d['shape']}")
        if not 0.01 <= d["size"] <= 3.0:
            issues.append(f"{name}: size 超出合理範圍 {d['size']}")
        if not 0.0 <= d["opacity"] <= 1.0:
            issues.append(f"{name}: opacity 需 0..1")
    return issues
