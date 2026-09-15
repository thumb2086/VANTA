"""
tools/vfx/sprites.py — 粒子精靈（sprite）的「參數化定義」
======================================================
不輸出大張 PNG，而是描述「怎麼畫」：每個精靈 = 基本shape + 參數。
Godot（procedural_texture.gd）與展示台（showcase/）實作同一組 shape，
因此同一份 JSON 在兩邊渲染出相同外观 —— 這是零依賴、可 diff、可測試的做法。

shape 清單（渲染層需實作者）：
  glow / star / ring / hex / shard / petal / glob / pixel / spark /
  smoke / wisp / feather / flame / crystal / dust
"""

from __future__ import annotations

SHAPES: tuple[str, ...] = (
    "glow", "star", "ring", "hex", "shard", "petal", "glob", "pixel",
    "spark", "smoke", "wisp", "feather", "flame", "crystal", "dust",
)


def _s(name: str, shape: str, color: str = "#ffffff", **kw) -> dict:
    assert shape in SHAPES, f"unknown shape {shape}"
    spec = {"name": name, "shape": shape, "color": color}
    spec.update(kw)
    return spec


SPRITES: dict[str, dict] = {
    # ── 通用 ──
    "sprite_glow": _s("sprite_glow", "glow", "#ffffff", softness=0.55, core=0.18),
    "sprite_flare": _s("sprite_flare", "star", "#fff3c8", points=6, inner=0.24,
                       softness=0.5, spikes=1.0),
    "sprite_star4": _s("sprite_star4", "star", "#ffffff", points=4, inner=0.2,
                       softness=0.45),
    "sprite_spark": _s("sprite_spark", "spark", "#fff0b0", arms=4, thickness=0.16),
    "sprite_smoke": _s("sprite_smoke", "smoke", "#b9bcc4", puffs=6, softness=0.75),
    "sprite_dust": _s("sprite_dust", "dust", "#c9c3b4", puffs=9, softness=0.85),
    "sprite_shard": _s("sprite_shard", "shard", "#e8f0ff", edges=5, sharpness=0.55),
    "sprite_glob": _s("sprite_glob", "glob", "#ffffff", softness=0.30, drip=0.35),
    "sprite_ring": _s("sprite_ring", "ring", "#ffffff", thickness=0.14, softness=0.3),
    "pixel": _s("pixel", "pixel", "#ffffff", blocks=5, gap=0.15),
    # ── 風格專用 ──
    "sprite_flame": _s("sprite_flame", "flame", "#ffd08a", flicker=0.4, taper=0.55),
    "sprite_soul": _s("sprite_soul", "wisp", "#d9a8ff", curl=0.55, tail=0.7),
    "sprite_tracer": _s("sprite_tracer", "glow", "#fff0c0", softness=0.28, elongate=6.0),
    "sprite_tracer_wisp": _s("sprite_tracer_wisp", "wisp", "#c690ff", curl=0.3,
                             tail=0.95, elongate=5.0),
    "sprite_tracer_light": _s("sprite_tracer_light", "glow", "#ffffff", softness=0.15,
                              elongate=9.0),
    "sprite_crystal": _s("sprite_crystal", "crystal", "#dff4ff", facets=6, sharpness=0.7),
    "sprite_petal": _s("sprite_petal", "petal", "#ffd8e2", curl=0.35, ratio=0.55),
    "sprite_feather": _s("sprite_feather", "feather", "#ffffff", barbs=7, ratio=0.32),
}


def sprite_names() -> list[str]:
    return sorted(SPRITES)


def resolve(name: str) -> dict:
    """找不到時退回通用光暈，避免單檔缺字造成整條管線失敗。"""
    return SPRITES.get(name or "", SPRITES["sprite_glow"])


def validate_sprites() -> list[str]:
    issues: list[str] = []
    for name, spec in SPRITES.items():
        if spec["shape"] not in SHAPES:
            issues.append(f"{name}: 未知 shape {spec['shape']}")
        if not str(spec["color"]).startswith("#"):
            issues.append(f"{name}: 顏色必須是 #rrggbb")
    return issues
