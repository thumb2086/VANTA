"""
tools/vfx/styles.py — 特效「風格（style）」定義
==============================================
一個風格 = 一整套視覺語彙（砲口焰 / 曳光 / 命中 / 擊殺 / 彈殼 / 煙霧 / 光暈），
槍皮只要指定 `style`，就自動取得一致的粒子蓝图（muzzle_<style>、tracer_<style>…）。

這樣做的好處：
  * 新增一套槍皮 = 指定 style + 調色，不需要動到渲染程式碼。
  * 客戶端只要實作 12 種風格，而不是 100+ 種特例。
"""

from __future__ import annotations

from typing import Any

# 每個風格的粒子參數模板（餵給 ParticleEmitter；未寫的欄位用預設值）
# 欄位語意見 tools/vfx/particles.py
STYLE_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    # ── 基準：實戰風格、無發光extras ──
    "default": {
        "muzzle": dict(kind="cone", count=14, speed=9.0, life=0.09, size=0.14, gravity=0.0,
                       color_start=(255, 246, 200), color_end=(255, 150, 60), cone_angle=26,
                       sprite="sprite_flare", emissive=2.0, light={"color": "#ffc070",
                       "energy": 3.0, "range": 3.0, "lifetime": 0.06}),
        "tracer": dict(kind="directional", count=1, speed=0.0, life=0.07, size=0.03,
                       color_start=(255, 248, 200), color_end=(255, 190, 90),
                       sprite="sprite_tracer", stretch=1.0, emissive=2.4, align="velocity"),
        "impact": dict(kind="cone", count=12, speed=5.5, life=0.35, size=0.05, gravity=6.0,
                       drag=1.6, color_start=(255, 240, 200), color_end=(190, 120, 60),
                       cone_angle=55, sprite="sprite_spark", decal="bullet_hole",
                       emissive=1.2),
        "kill": dict(kind="sphere", count=34, speed=5.5, life=0.75, size=0.09, gravity=-1.4,
                     drag=1.1, color_start=(255, 226, 130), color_end=(255, 70, 60),
                     sprite="sprite_glow", emissive=2.2, banner="kill_default"),
        "smoke": dict(kind="sphere", count=10, speed=1.1, life=0.75, size=0.35, gravity=-0.3,
                      drag=2.0, color_start=(150, 150, 150), color_end=(60, 60, 60),
                      alpha_curve=(0.0, 0.45, 0.0), additive=False, sprite="sprite_smoke"),
    },
    # ── 掠奪者：紫黑靈魂、吞噬感 ──
    "soul": {
        "muzzle": dict(kind="cone", count=18, speed=7.0, life=0.16, size=0.16, gravity=-1.0,
                       color_start=(230, 170, 255), color_end=(90, 20, 140), cone_angle=34,
                       sprite="sprite_soul", emissive=3.2, turbulence=1.4,
                       light={"color": "#a347ff", "energy": 5.0, "range": 4.0, "lifetime": 0.12}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.14, size=0.055,
                       color_start=(200, 120, 255), color_end=(60, 10, 90),
                       sprite="sprite_tracer_wisp", stretch=1.4, emissive=3.0,
                       turbulence=0.7, align="velocity"),
        "impact": dict(kind="cone", count=16, speed=4.2, life=0.5, size=0.07, gravity=-1.2,
                       drag=2.4, color_start=(190, 110, 255), color_end=(40, 8, 70),
                       cone_angle=70, sprite="sprite_soul", decal="burn_hole",
                       emissive=2.4, sub="smoke_void"),
        "kill": dict(kind="sphere", count=46, speed=3.6, life=1.15, size=0.11, gravity=-2.2,
                     drag=1.6, color_start=(206, 130, 255), color_end=(30, 6, 55),
                     sprite="sprite_soul", emissive=3.0, turbulence=1.0,
                     size_curve=(1.0, 1.25, 0.2), banner="kill_reaver",
                     light={"color": "#8b30d8", "energy": 4.0, "range": 6.0, "lifetime": 0.5}),
        "smoke": dict(kind="sphere", count=12, speed=0.9, life=1.1, size=0.42, gravity=-0.4,
                      drag=2.2, color_start=(90, 40, 130), color_end=(20, 6, 40),
                      alpha_curve=(0.0, 0.5, 0.0), additive=False, sprite="sprite_smoke"),
    },
    # ── 貴族：金橙能量環 ──
    "energy": {
        "muzzle": dict(kind="cone", count=16, speed=10.0, life=0.11, size=0.15,
                       color_start=(255, 232, 160), color_end=(255, 140, 30), cone_angle=24,
                       sprite="sprite_ring", emissive=3.4,
                       light={"color": "#ffb03a", "energy": 4.0, "range": 3.5, "lifetime": 0.08}),
        "tracer": dict(kind="directional", count=2, speed=0.0, life=0.10, size=0.04,
                       color_start=(255, 210, 120), color_end=(255, 130, 20),
                       sprite="sprite_tracer", stretch=1.2, emissive=3.0, align="velocity"),
        "impact": dict(kind="cone", count=16, speed=6.5, life=0.4, size=0.06, gravity=3.0,
                       drag=1.4, color_start=(255, 225, 150), color_end=(200, 100, 20),
                       cone_angle=95, sprite="sprite_ring", decal="scorch_ring", emissive=2.4),
        "kill": dict(kind="sphere", count=40, speed=6.0, life=0.9, size=0.10, gravity=-0.8,
                     drag=1.2, color_start=(255, 226, 130), color_end=(220, 110, 20),
                     sprite="sprite_glow", emissive=3.2, size_curve=(0.6, 1.2, 0.1),
                     banner="kill_prime"),
        "smoke": dict(kind="sphere", count=9, speed=1.0, life=0.8, size=0.3, gravity=-0.2,
                      drag=2.0, color_start=(190, 150, 90), color_end=(60, 40, 20),
                      alpha_curve=(0.0, 0.4, 0.0), additive=False, sprite="sprite_smoke"),
    },
    # ── 光之哨兵：聖白光翼 ──
    "holy": {
        "muzzle": dict(kind="cone", count=15, speed=8.5, life=0.13, size=0.17,
                       color_start=(255, 255, 255), color_end=(150, 200, 255), cone_angle=30,
                       sprite="sprite_star4", emissive=3.6,
                       light={"color": "#cfe6ff", "energy": 4.2, "range": 4.0, "lifetime": 0.1}),
        "tracer": dict(kind="directional", count=2, speed=0.0, life=0.12, size=0.05,
                       color_start=(255, 255, 255), color_end=(160, 205, 255),
                       sprite="sprite_tracer_light", stretch=1.6, emissive=3.2, align="velocity"),
        "impact": dict(kind="cone", count=14, speed=5.0, life=0.45, size=0.06, gravity=0.5,
                       drag=2.0, color_start=(255, 255, 255), color_end=(140, 190, 255),
                       cone_angle=80, sprite="sprite_star4", decal="holy_mark", emissive=2.8),
        "kill": dict(kind="sphere", count=42, speed=4.2, life=1.05, size=0.10, gravity=-2.6,
                     drag=1.4, color_start=(255, 255, 255), color_end=(120, 180, 255),
                     sprite="sprite_feather", emissive=3.0, size_curve=(0.7, 1.15, 0.35),
                     banner="kill_sentinels"),
        "smoke": dict(kind="sphere", count=10, speed=0.8, life=1.0, size=0.36, gravity=-0.6,
                      color_start=(235, 240, 255), color_end=(160, 190, 235),
                      alpha_curve=(0.0, 0.45, 0.0), additive=False, sprite="sprite_smoke"),
    },
    # ── 龍炎：龍口噴焰 ──
    "dragon": {
        "muzzle": dict(kind="cone", count=22, speed=11.0, life=0.18, size=0.20,
                       color_start=(255, 235, 170), color_end=(255, 90, 20), cone_angle=32,
                       sprite="sprite_flame", emissive=3.6, turbulence=0.8,
                       light={"color": "#ff7a2a", "energy": 5.0, "range": 4.5, "lifetime": 0.14}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.16, size=0.07,
                       color_start=(255, 190, 90), color_end=(210, 60, 20),
                       sprite="sprite_flame", stretch=1.1, emissive=3.0, turbulence=0.5),
        "impact": dict(kind="cone", count=18, speed=7.0, life=0.5, size=0.09, gravity=7.5,
                       drag=1.2, color_start=(255, 210, 120), color_end=(180, 60, 20),
                       cone_angle=65, sprite="sprite_flame", decal="burn_hole",
                       emissive=2.6, sub="smoke_ember"),
        "kill": dict(kind="sphere", count=48, speed=6.5, life=1.0, size=0.13, gravity=1.0,
                     drag=1.0, color_start=(255, 200, 110), color_end=(150, 30, 10),
                     sprite="sprite_flame", emissive=3.0, banner="kill_dragon"),
        "smoke": dict(kind="sphere", count=12, speed=1.4, life=1.2, size=0.45, gravity=-0.2,
                      color_start=(90, 60, 45), color_end=(30, 20, 15), alpha_curve=(0, .5, 0),
                      additive=False, sprite="sprite_smoke"),
    },
    # ── 暗影龍焰（活體）：熔岩呼吸 ──
    "breath": {
        "muzzle": dict(kind="cone", count=26, speed=9.0, life=0.24, size=0.22, gravity=-1.0,
                       color_start=(255, 200, 120), color_end=(200, 30, 10), cone_angle=40,
                       sprite="sprite_flame", emissive=4.0, turbulence=1.2,
                       light={"color": "#ff5b18", "energy": 6.0, "range": 5.0, "lifetime": 0.2}),
        "tracer": dict(kind="directional", count=4, speed=0.0, life=0.2, size=0.08,
                       color_start=(255, 170, 80), color_end=(150, 30, 10),
                       sprite="sprite_flame", stretch=1.0, emissive=3.4, turbulence=0.9),
        "impact": dict(kind="cone", count=20, speed=6.0, life=0.6, size=0.11, gravity=8.0,
                       color_start=(255, 180, 90), color_end=(120, 20, 8), cone_angle=70,
                       sprite="sprite_flame", decal="melt_hole", emissive=3.0,
                       sub="smoke_ember"),
        "kill": dict(kind="sphere", count=54, speed=5.0, life=1.25, size=0.15, gravity=-0.6,
                     drag=0.9, color_start=(255, 190, 100), color_end=(90, 12, 6),
                     sprite="sprite_flame", emissive=3.4, banner="kill_elderflame",
                     size_curve=(0.8, 1.3, 0.15)),
        "smoke": dict(kind="sphere", count=14, speed=1.2, life=1.4, size=0.5, gravity=-0.3,
                      color_start=(120, 60, 40), color_end=(25, 12, 10),
                      alpha_curve=(0, .55, 0), additive=False, sprite="sprite_smoke"),
    },
    # ── 源計畫：資料故障 ──
    "glitch": {
        "muzzle": dict(kind="cone", count=16, speed=12.0, life=0.1, size=0.13,
                       color_start=(120, 255, 235), color_end=(255, 47, 176), cone_angle=20,
                       sprite="pixel", emissive=4.0, turbulence=2.0,
                       light={"color": "#00ffd0", "energy": 4.0, "range": 3.5, "lifetime": 0.07}),
        "tracer": dict(kind="directional", count=4, speed=0.0, life=0.09, size=0.05,
                       color_start=(0, 245, 200), color_end=(255, 47, 176), sprite="pixel",
                       stretch=0.8, emissive=3.6, turbulence=2.6, align="velocity"),
        "impact": dict(kind="cone", count=18, speed=6.0, life=0.35, size=0.055, gravity=2.0,
                       drag=2.6, color_start=(120, 255, 235), color_end=(255, 47, 176),
                       cone_angle=90, sprite="pixel", decal="pixel_burn", emissive=3.0),
        "kill": dict(kind="sphere", count=44, speed=5.0, life=0.85, size=0.08, gravity=1.5,
                     drag=1.8, color_start=(0, 245, 200), color_end=(255, 47, 176),
                     sprite="pixel", emissive=3.4, turbulence=2.2, banner="kill_glitchpop"),
        "smoke": dict(kind="sphere", count=10, speed=1.0, life=0.6, size=0.26,
                      color_start=(60, 90, 120), color_end=(20, 30, 50),
                      alpha_curve=(0, .4, 0), additive=False, sprite="pixel"),
    },
    # ── 离子：過曝雷射 ──
    "laser": {
        "muzzle": dict(kind="cone", count=10, speed=14.0, life=0.07, size=0.10,
                       color_start=(255, 245, 220), color_end=(255, 150, 60), cone_angle=12,
                       sprite="sprite_glow", emissive=4.5,
                       light={"color": "#ffb04d", "energy": 3.6, "range": 3.0, "lifetime": 0.05}),
        "tracer": dict(kind="directional", count=1, speed=0.0, life=0.06, size=0.022,
                       color_start=(255, 250, 235), color_end=(255, 160, 70),
                       sprite="sprite_tracer", stretch=2.0, emissive=5.0, align="velocity"),
        "impact": dict(kind="cone", count=12, speed=8.0, life=0.28, size=0.045, gravity=1.0,
                       drag=2.2, color_start=(255, 240, 210), color_end=(255, 140, 50),
                       cone_angle=100, sprite="sprite_glow", decal="melt_hole", emissive=3.4),
        "kill": dict(kind="sphere", count=36, speed=7.0, life=0.7, size=0.07, gravity=0.0,
                     drag=2.0, color_start=(255, 245, 220), color_end=(255, 150, 60),
                     sprite="sprite_glow", emissive=4.0, banner="kill_ion"),
        "smoke": dict(kind="sphere", count=8, speed=0.9, life=0.7, size=0.24,
                      color_start=(200, 200, 210), color_end=(80, 80, 90),
                      alpha_curve=(0, .35, 0), additive=False, sprite="sprite_smoke"),
    },
    # ── 冰霜紀元：結晶碎冰 ──
    "frost": {
        "muzzle": dict(kind="cone", count=14, speed=8.0, life=0.16, size=0.13, gravity=-0.5,
                       color_start=(235, 250, 255), color_end=(90, 170, 235), cone_angle=42,
                       sprite="sprite_crystal", emissive=2.8,
                       light={"color": "#8fd8ff", "energy": 3.4, "range": 3.5, "lifetime": 0.12}),
        "tracer": dict(kind="directional", count=2, speed=0.0, life=0.12, size=0.045,
                       color_start=(220, 245, 255), color_end=(110, 180, 230),
                       sprite="sprite_crystal", stretch=1.0, emissive=2.4),
        "impact": dict(kind="cone", count=20, speed=6.0, life=0.55, size=0.06, gravity=7.0,
                       drag=0.6, color_start=(225, 248, 255), color_end=(90, 150, 200),
                       cone_angle=85, sprite="sprite_crystal", decal="frost_crack",
                       emissive=1.6, sub="smoke_frost"),
        "kill": dict(kind="sphere", count=44, speed=5.5, life=0.95, size=0.09, gravity=3.5,
                     drag=1.0, color_start=(225, 248, 255), color_end=(80, 140, 200),
                     sprite="sprite_crystal", emissive=2.2, banner="kill_freeze"),
        "smoke": dict(kind="sphere", count=12, speed=1.0, life=1.0, size=0.4, gravity=-0.3,
                      color_start=(215, 235, 245), color_end=(120, 150, 175),
                      alpha_curve=(0, .5, 0), additive=False, sprite="sprite_smoke"),
    },
    # ── 毒蛇：腐蝕毒液 ──
    "venom": {
        "muzzle": dict(kind="cone", count=16, speed=7.0, life=0.2, size=0.15, gravity=1.5,
                       color_start=(180, 255, 130), color_end=(30, 140, 60), cone_angle=40,
                       sprite="sprite_glob", emissive=2.8,
                       light={"color": "#4dff8a", "energy": 3.4, "range": 3.5, "lifetime": 0.14}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.15, size=0.06,
                       color_start=(170, 255, 120), color_end=(30, 130, 50),
                       sprite="sprite_glob", stretch=0.9, emissive=2.4, turbulence=0.8),
        "impact": dict(kind="cone", count=16, speed=4.5, life=0.6, size=0.08, gravity=9.5,
                       drag=0.4, color_start=(180, 255, 130), color_end=(20, 110, 45),
                       cone_angle=60, sprite="sprite_glob", decal="acid_burn", emissive=2.0,
                       sub="smoke_toxic"),
        "kill": dict(kind="sphere", count=40, speed=4.0, life=1.1, size=0.12, gravity=4.0,
                     drag=0.8, color_start=(170, 255, 120), color_end=(20, 90, 40),
                     sprite="sprite_glob", emissive=2.2, banner="kill_melt"),
        "smoke": dict(kind="sphere", count=14, speed=0.9, life=1.3, size=0.5, gravity=-0.2,
                      color_start=(90, 180, 90), color_end=(20, 60, 30), alpha_curve=(0, .5, 0),
                      additive=False, sprite="sprite_smoke"),
    },
    # ── 星塵：細碎星光 ──
    "stardust": {
        "muzzle": dict(kind="cone", count=16, speed=7.5, life=0.18, size=0.10,
                       color_start=(215, 225, 255), color_end=(90, 110, 235), cone_angle=48,
                       sprite="sprite_star4", emissive=3.0, turbulence=0.9,
                       light={"color": "#8ea0ff", "energy": 3.0, "range": 3.0, "lifetime": 0.12}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.14, size=0.04,
                       color_start=(205, 215, 255), color_end=(90, 105, 220),
                       sprite="sprite_star4", stretch=1.0, emissive=2.6, turbulence=0.6),
        "impact": dict(kind="cone", count=18, speed=4.5, life=0.6, size=0.05, gravity=1.0,
                       drag=2.0, color_start=(215, 225, 255), color_end=(70, 85, 200),
                       cone_angle=95, sprite="sprite_star4", decal="stardust_dust",
                       emissive=2.2),
        "kill": dict(kind="sphere", count=50, speed=4.5, life=1.15, size=0.07, gravity=-0.4,
                     drag=1.6, color_start=(225, 232, 255), color_end=(80, 95, 220),
                     sprite="sprite_star4", emissive=2.8, banner="kill_nova"),
        "smoke": dict(kind="sphere", count=10, speed=0.7, life=1.2, size=0.35,
                      color_start=(120, 130, 200), color_end=(30, 32, 60), alpha_curve=(0, .4, 0),
                      additive=False, sprite="sprite_smoke"),
    },
    # ── 熔核：岩漿碎塊 ──
    "magma": {
        "muzzle": dict(kind="cone", count=18, speed=9.5, life=0.15, size=0.17, gravity=2.0,
                       color_start=(255, 210, 140), color_end=(230, 60, 20), cone_angle=38,
                       sprite="sprite_glob", emissive=3.6,
                       light={"color": "#ff6a2a", "energy": 5.0, "range": 4.0, "lifetime": 0.1}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.16, size=0.065,
                       color_start=(255, 150, 60), color_end=(140, 30, 10),
                       sprite="sprite_glob", stretch=0.8, emissive=3.0, turbulence=0.7),
        "impact": dict(kind="cone", count=20, speed=7.5, life=0.6, size=0.09, gravity=11.0,
                       drag=0.5, color_start=(255, 200, 120), color_end=(120, 30, 12),
                       cone_angle=60, sprite="sprite_glob", decal="melt_hole", emissive=2.8,
                       sub="smoke_ember"),
        "kill": dict(kind="sphere", count=46, speed=6.5, life=1.0, size=0.12, gravity=8.0,
                     drag=0.8, color_start=(255, 180, 90), color_end=(110, 22, 10),
                     sprite="sprite_glob", emissive=3.0, banner="kill_core"),
        "smoke": dict(kind="sphere", count=12, speed=1.1, life=1.1, size=0.42, gravity=-0.2,
                      color_start=(110, 70, 55), color_end=(30, 18, 14), alpha_curve=(0, .5, 0),
                      additive=False, sprite="sprite_smoke"),
    },
    # ── 彼岸花：落櫻與刀光 ──
    "petal": {
        "muzzle": dict(kind="cone", count=16, speed=6.5, life=0.22, size=0.12, gravity=1.0,
                       color_start=(255, 230, 235), color_end=(226, 60, 90), cone_angle=55,
                       sprite="sprite_petal", emissive=1.8, spin=140.0, turbulence=0.8,
                       light={"color": "#ff8aa0", "energy": 2.6, "range": 3.0, "lifetime": 0.14}),
        "tracer": dict(kind="directional", count=3, speed=0.0, life=0.18, size=0.05,
                       color_start=(255, 215, 225), color_end=(230, 90, 120),
                       sprite="sprite_petal", stretch=0.7, emissive=1.6, spin=90.0),
        "impact": dict(kind="cone", count=18, speed=4.0, life=0.7, size=0.06, gravity=6.0,
                       drag=1.6, color_start=(255, 225, 232), color_end=(215, 70, 100),
                       cone_angle=80, sprite="sprite_petal", decal="petal_mark", spin=180.0,
                       emissive=1.2),
        "kill": dict(kind="sphere", count=52, speed=4.0, life=1.35, size=0.09, gravity=3.0,
                     drag=1.4, color_start=(255, 225, 232), color_end=(210, 40, 70),
                     sprite="sprite_petal", spin=200.0, emissive=1.6, banner="kill_bloom"),
        "smoke": dict(kind="sphere", count=8, speed=0.6, life=1.3, size=0.3, gravity=0.5,
                      color_start=(240, 220, 225), color_end=(180, 140, 150),
                      alpha_curve=(0, .4, 0), additive=False, sprite="sprite_petal"),
    },
}

# 風格 → 展示／UI 用中繼資料
STYLE_META: dict[str, dict[str, Any]] = {
    "default": {"label": "基準", "color": "#9aa3b2"},
    "soul": {"label": "噬魂", "color": "#a347ff"},
    "energy": {"label": "能量", "color": "#ffb020"},
    "holy": {"label": "聖光", "color": "#9fd0ff"},
    "dragon": {"label": "龍焰", "color": "#ff8a3a"},
    "breath": {"label": "活體龍焰", "color": "#ff5b18"},
    "glitch": {"label": "故障", "color": "#00f5c8"},
    "laser": {"label": "雷射", "color": "#ffd08a"},
    "frost": {"label": "冰霜", "color": "#8fd8ff"},
    "venom": {"label": "毒液", "color": "#4dff8a"},
    "stardust": {"label": "星塵", "color": "#8ea0ff"},
    "magma": {"label": "熔核", "color": "#ff6a2a"},
    "petal": {"label": "落櫻", "color": "#ff9aa8"},
}


def style_names() -> list[str]:
    return sorted(STYLE_PRESETS)


def is_style(name: str) -> bool:
    return name in STYLE_PRESETS


def slots_for(style: str) -> dict[str, str]:
    """風格 → 四個槽位的粒子蓝图名稱（muzzle/tracer/impact/kill）。"""
    if style not in STYLE_PRESETS:
        style = "default"
    return {k: f"{k}_{style}" for k in ("muzzle", "tracer", "impact", "kill")}
