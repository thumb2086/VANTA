"""
tools/vfx/blueprints.py — 分層特效蓝图（layered VFX blueprints）
=============================================================
一個「特效」不是單一粒子，而是一組分層元件：

    layers = [ particles | mesh | light | decal | sound | camera | hud ]

客戶端 `FxManager` 以同一套語意播放（Godot 與網頁展示台共用），
槍皮只負責指定風格（style）與顏色覆蓋，因此新增特效不需要改渲染程式碼。

圖層欄位說明：
    type     : 必要，見上
    preset   : particles → PRESETS 名稱；light/decal/sound 同理指向各自註冊表
    slot     : 從「槍皮风格」取的槽位（muzzle/tracer/impact/kill/smoke）
    at       : 位置語意 muzzle / impact / world / camera / weapon / origin
    delay    : 相對啟動時間（秒）
    follow   : 是否跟隨發射源（砲口焰需跟槍）
    color_key: 從槍皮 fx 覆寫顏色的欄位名（例：muzzle_color）
    scale    : 尺寸乘子（會被武器的 muzzle_scale 再乘一次）
    count    : 覆寫粒子數量
    ttl      : 存活時間（mesh/light/decal）
"""

from __future__ import annotations

from typing import Any

from tools.vfx import styles

# 武器射擊的「通用」圖層模板：風格決定實際粒子蓝图
SHOT_LAYERS: list[dict] = [
    {"type": "particles", "slot": "muzzle", "at": "muzzle", "follow": True,
     "color_key": "muzzle_color", "scale_key": "muzzle_scale", "delay": 0.0},
    {"type": "particles", "preset": "muzzle_smoke", "at": "muzzle", "follow": True,
     "delay": 0.01, "color_key": "smoke_color", "when_smoke": True},
    {"type": "particles", "preset": "muzzle_sparks", "at": "muzzle", "delay": 0.0,
     "color_key": "muzzle_color", "scale": 0.9},
    {"type": "light", "at": "muzzle", "color_key": "light_color",
     "energy_key": "light_energy", "range": 4.0, "ttl_key": None, "ttl": 0.07},
    {"type": "particles", "slot": "tracer", "at": "tracer", "color_key": "tracer_color",
     "scale_key": "tracer_width"},
    {"type": "particles", "preset": "shell_casing", "at": "eject", "delay": 0.02},
]

IMPACT_LAYERS: list[dict] = [
    {"type": "particles", "slot": "impact", "at": "impact", "color_key": "impact_color",
     "delay": 0.0},
    {"type": "mesh", "preset": "shockwave", "at": "impact", "scale": 0.55, "ttl": 0.28,
     "color_key": "impact_color", "when_style": ("energy", "holy", "laser", "soul", "magma")},
    {"type": "decal", "preset_key": "decal", "at": "impact", "scale": 1.0, "delay": 0.0},
    {"type": "particles", "preset": "impact_wall", "at": "impact", "scale": 0.7},
    {"type": "light", "at": "impact", "color_key": "impact_color", "energy": 1.6,
     "range": 2.2, "ttl": 0.06},
]

KILL_LAYERS: list[dict] = [
    {"type": "particles", "slot": "kill", "at": "victim", "color_key": "kill_color",
     "delay": 0.0},
    {"type": "hud", "preset": "kill_banner", "at": "screen",
     "frame_key": "banner_frame", "color_key": "kill_color", "style_key": "kill_style"},
    {"type": "camera", "preset": "shake", "trauma": 0.16, "ttl": 0.32, "at": "screen"},
    {"type": "light", "at": "victim", "color_key": "kill_color", "energy": 4.5,
     "range": 5.0, "ttl": 0.45},
]


def _sig(layer: dict) -> tuple:
    return tuple(sorted((k, str(v)) for k, v in layer.items()))


def _style_for(name: str, default: str = "default") -> str:
    return name if name in styles.STYLE_PRESETS else default


def build_blueprints() -> dict[str, dict]:
    """展開成完整蓝图表（每個風格一組 shot/impact/kill ＋共通特效）。"""
    out: dict[str, dict] = {}

    # ── 風格化三件套 ──
    for style in sorted(styles.STYLE_PRESETS):
        meta = styles.STYLE_META.get(style, {})
        out[f"shot_{style}"] = {
            "id": f"shot_{style}", "kind": "shot", "style": style,
            "duration": 0.42, "budget": 2 if style != "default" else 1,
            "layers": [dict(l) for l in SHOT_LAYERS],
            "label": f"{meta.get('label', style)}射擊",
            "audio": {"slot": "fire", "pitch_key": "sound_pitch", "gain_key": "sound_gain_db",
                      "override_key": "sound_key"},
        }
        out[f"impact_{style}"] = {
            "id": f"impact_{style}", "kind": "impact", "style": style,
            "duration": 0.6, "budget": 2 if style != "default" else 1,
            "layers": [dict(l) for l in IMPACT_LAYERS],
            "label": f"{meta.get('label', style)}命中",
            "audio": {"sfx": "body_hit", "pitch": 1.0, "gain_db": -6.0},
        }
        out[f"kill_{style}"] = {
            "id": f"kill_{style}", "kind": "kill", "style": style,
            "duration": 1.25, "budget": 3 if style != "default" else 2,
            "layers": [dict(l) for l in KILL_LAYERS],
            "label": f"{meta.get('label', style)}擊殺",
            "audio": {"sfx": "kill_confirm", "pitch": 1.0},
        }

    # ── 共通／玩法特效 ──
    common: dict[str, dict[str, Any]] = {
        "ult_ready": {
            "kind": "common", "style": "default",
            "label": "終點球就緒",
            "duration": 1.15, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "shield_ring", "at": "world"},
                {"type": "light", "at": "world", "color": "#ffce54",
                 "energy": 6.0, "range": 9.0, "ttl": 1.1},
            ],
            "audio": {"sfx": "ult_ready_chime", "pitch": 1.0, "gain_db": -3.0},
        },
        "ult_cast": {
            "kind": "common", "style": "default",
            "label": "終點球施放",
            "duration": 0.95, "budget": 3,
            "layers": [
                {"type": "particles", "preset": "spike_shockwave", "at": "world"},
                {"type": "particles", "preset": "shield_ring", "at": "world", "scale": 1.6},
                {"type": "light", "at": "world", "color": "#ff8a3c",
                 "energy": 16.0, "range": 22.0, "ttl": 0.5},
            ],
            "audio": {"sfx": "ult_cast", "pitch": 1.0, "gain_db": -2.0},
        },
        "hit_marker": {
            "duration": 0.22, "budget": 1,
            "layers": [
                {"type": "hud", "preset": "hitmarker", "at": "screen", "ttl": 0.22},
                {"type": "particles", "preset": "hit_marker", "at": "impact", "scale": 0.6},
            ],
            "audio": {"sfx": "body_hit", "pitch": 1.35, "gain_db": -8.0},
            "label": "命中回饋",
        },
        "headshot_marker": {
            "duration": 0.34, "budget": 2,
            "layers": [
                {"type": "hud", "preset": "hitmarker_headshot", "at": "screen", "ttl": 0.3},
                {"type": "particles", "preset": "headshot_shatter", "at": "impact"},
                {"type": "camera", "preset": "punch", "trauma": 0.10, "ttl": 0.22, "at": "screen"},
            ],
            "audio": {"sfx": "headshot_confirm", "pitch": 1.0},
            "label": "爆頭回饋",
        },
        "ricochet": {
            "duration": 0.45, "budget": 1,
            "layers": [
                {"type": "particles", "preset": "ricochet", "at": "impact"},
                {"type": "decal", "preset": "ricochet_mark", "at": "impact"},
                {"type": "sound", "sfx": "trap_trigger", "pitch": 1.7, "gain_db": -10.0},
            ],
            "label": "跳彈",
        },
        "flesh_hit": {
            "duration": 0.5, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "impact_flesh", "at": "impact"},
                {"type": "particles", "preset": "blood_mist", "at": "impact", "scale": 0.9},
                {"type": "decal", "preset": "blood_spatter", "at": "impact"},
            ],
            "audio": {"sfx": "body_hit", "pitch": 0.92, "gain_db": -3.0},
            "label": "命中肉體",
        },
        "glass_break": {
            "duration": 0.6, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "impact_glass", "at": "impact"},
                {"type": "decal", "preset": "glass_crack", "at": "impact"},
                {"type": "hud", "preset": "flash_white", "at": "screen", "ttl": 0.12,
                 "intensity": 0.15},
            ],
            "label": "玻璃破裂",
        },
        "shell_drop": {
            "duration": 1.2, "budget": 1,
            "layers": [{"type": "particles", "preset": "shell_casing", "at": "eject"}],
            "label": "彈殼",
        },
        "knife_swing": {
            "duration": 0.34, "budget": 1,
            "layers": [
                {"type": "mesh", "preset": "slash_arc", "at": "muzzle", "scale": 1.0,
                 "ttl": 0.20, "color_key": "tracer_color"},
                {"type": "particles", "slot": "tracer", "at": "muzzle", "scale": 0.8,
                 "count": 8},
            ],
            "audio": {"sfx": "knife_swing", "pitch": 1.0},
            "label": "近戰揮砍",
        },
        "knife_hit": {
            "duration": 0.5, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "impact_flesh", "at": "impact", "scale": 1.2},
                {"type": "particles", "slot": "kill", "at": "impact", "scale": 0.7,
                 "color_key": "kill_color"},
                {"type": "decal", "preset": "blood_hole", "at": "impact"},
                {"type": "camera", "preset": "punch", "trauma": 0.22, "ttl": 0.3, "at": "screen"},
            ],
            "audio": {"sfx": "knife_hit", "pitch": 1.0},
            "label": "近戰命中",
        },
        "spike_plant": {
            "duration": 1.8, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "spike_pulse", "at": "world", "loop": True},
                {"type": "light", "at": "world", "color": "#ff5a3a", "energy": 3.0,
                 "range": 5.0, "ttl": 1.8},
                {"type": "hud", "preset": "spike_banner", "at": "screen"},
            ],
            "audio": {"sfx": "spike_planted", "pitch": 1.0},
            "label": "Spike 安放",
        },
        "spike_explode": {
            "duration": 2.2, "budget": 3,
            "layers": [
                {"type": "particles", "preset": "spike_shockwave", "at": "world"},
                {"type": "particles", "preset": "explosion_debris", "at": "world", "scale": 2.2},
                {"type": "particles", "preset": "ember_float", "at": "world", "loop": True},
                {"type": "mesh", "preset": "shockwave", "at": "world", "scale": 9.0, "ttl": 0.9,
                 "color": "#ffb060"},
                {"type": "light", "at": "world", "color": "#ff8a3a", "energy": 22.0,
                 "range": 40.0, "ttl": 0.6},
                {"type": "camera", "preset": "shake", "trauma": 1.0, "ttl": 1.1, "at": "screen"},
                {"type": "hud", "preset": "flash_white", "at": "screen", "ttl": 0.5,
                 "intensity": 0.9},
            ],
            "audio": {"sfx": "spike_exploded", "pitch": 0.9},
            "label": "Spike 爆擊",
        },
        "ability_smoke": {
            "duration": 1.4, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "smoke_bloom", "at": "world"},
                {"type": "mesh", "preset": "smoke_dome", "at": "world", "scale": 1.0,
                 "ttl": 1.3, "color": "#8f96a3"},
            ],
            "audio": {"sfx": "smoke_puff", "pitch": 1.0},
            "label": "煙霧展開",
        },
        "ability_flash": {
            "duration": 0.7, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "flash_pop", "at": "world"},
                {"type": "light", "at": "world", "color": "#ffffff", "energy": 12.0,
                 "range": 18.0, "ttl": 0.3},
                {"type": "hud", "preset": "flash_white", "at": "screen", "ttl": 0.55,
                 "intensity": 0.85},
            ],
            "audio": {"sfx": "flash_explode", "pitch": 1.0},
            "label": "閃光彈",
        },
        "ability_frag": {
            "duration": 1.0, "budget": 3,
            "layers": [
                {"type": "particles", "preset": "explosion_debris", "at": "world"},
                {"type": "mesh", "preset": "shockwave", "at": "world", "scale": 3.0,
                 "ttl": 0.5, "color": "#ffb060"},
                {"type": "light", "at": "world", "color": "#ff8a3a", "energy": 10.0,
                 "range": 14.0, "ttl": 0.35},
                {"type": "camera", "preset": "shake", "trauma": 0.45, "ttl": 0.6,
                 "at": "screen"},
            ],
            "audio": {"sfx": "explosion", "pitch": 0.95},
            "label": "破片爆擊",
        },
        "ability_heal": {
            "duration": 1.2, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "heal_aura", "at": "victim"},
                {"type": "light", "at": "victim", "color": "#4dffa0", "energy": 2.4,
                 "range": 3.5, "ttl": 1.0},
                {"type": "hud", "preset": "heal_pop", "at": "screen", "ttl": 0.4},
            ],
            "audio": {"sfx": "ability_cast", "pitch": 1.18},
            "label": "治療",
        },
        "ability_dash": {
            "duration": 0.5, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "dash_trail", "at": "weapon", "loop": False},
                {"type": "mesh", "preset": "speed_lines", "at": "camera", "scale": 1.0,
                 "ttl": 0.3, "color": "#9fd0ff"},
                {"type": "camera", "preset": "kick", "trauma": 0.12, "ttl": 0.25, "at": "screen"},
            ],
            "audio": {"sfx": "ability_cast", "pitch": 1.35},
            "label": "衝刺",
        },
        "reload_done": {
            "duration": 0.3, "budget": 1,
            "layers": [{"type": "particles", "preset": "spark", "at": "weapon", "count": 4,
                        "scale": 0.35}],
            "audio": {"sfx": "slide_rack", "pitch": 1.0, "gain_db": -4.0},
            "label": "換彈完成",
        },
        "round_win": {
            "duration": 1.6, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "banner_sparkle", "at": "camera"},
                {"type": "hud", "preset": "round_banner_win", "at": "screen", "ttl": 2.4},
            ],
            "audio": {"sfx": "round_win", "pitch": 1.0},
            "label": "回合勝利",
        },
        "round_loss": {
            "duration": 1.6, "budget": 2,
            "layers": [
                {"type": "hud", "preset": "round_banner_loss", "at": "screen", "ttl": 2.4},
                {"type": "camera", "preset": "desaturate", "amount": 0.45, "ttl": 1.2,
                 "at": "screen"},
            ],
            "audio": {"sfx": "round_loss", "pitch": 1.0},
            "label": "回合敗北",
        },
        "death": {
            "duration": 1.0, "budget": 2,
            "layers": [
                {"type": "particles", "preset": "blood_mist", "at": "victim", "scale": 1.6},
                {"type": "camera", "preset": "slowmo", "amount": 0.35, "ttl": 0.9, "at": "screen"},
                {"type": "hud", "preset": "damage_vignette", "at": "screen", "ttl": 1.2,
                 "intensity": 1.0},
            ],
            "audio": {"sfx": "damage_taken", "pitch": 0.8, "gain_db": -2.0},
            "label": "陣亡",
        },
    }
    for name, spec in common.items():
        out[name] = {"id": name, "kind": "common", "style": "default",
                     "label": spec.get("label", name), **spec}
    return out


BLUEPRINTS: dict[str, dict] = build_blueprints()

# 所有可用的圖層類型（渲染層需逐一處理；未處理的類型應安靜忽略而非崩潰）
LAYER_TYPES: tuple[str, ...] = ("particles", "mesh", "light", "decal", "sound", "camera", "hud")

# mesh 預設件（客戶端以程序化網格實作）
MESH_PRIMITIVES: dict[str, dict] = {
    "shockwave": {"geometry": "ring", "color": "#ffd9a0", "energy": 2.0, "grow": 3.2,
                  "fade": "quad_out", "additive": True},
    "slash_arc": {"geometry": "arc", "color": "#e8f0ff", "energy": 2.4, "grow": 1.1,
                  "fade": "linear", "additive": True},
    "smoke_dome": {"geometry": "sphere", "color": "#8f96a3", "energy": 0.0, "grow": 1.0,
                   "fade": "hold", "additive": False},
    "speed_lines": {"geometry": "lines", "color": "#cfe6ff", "energy": 1.6, "grow": 1.0,
                    "fade": "quad_out", "additive": True},
}


def blueprint_names() -> list[str]:
    return sorted(BLUEPRINTS)


def get(name: str) -> dict | None:
    return BLUEPRINTS.get(name)


def for_shot(style: str) -> dict:
    return BLUEPRINTS.get(f"shot_{_style_for(style)}", BLUEPRINTS["shot_default"])


def for_impact(style: str) -> dict:
    return BLUEPRINTS.get(f"impact_{_style_for(style)}", BLUEPRINTS["impact_default"])


def for_kill(style: str) -> dict:
    return BLUEPRINTS.get(f"kill_{_style_for(style)}", BLUEPRINTS["kill_default"])


def validate_blueprints() -> list[str]:
    """確認蓝图引用的粒子／貼花／音效／網格件都存在。"""
    from tools.sfx.synth import SFX_REGISTRY
    from tools.vfx.decals import DECALS
    from tools.vfx.particles import PRESETS

    issues: list[str] = []
    for name, bp in BLUEPRINTS.items():
        if bp.get("duration", 0) <= 0:
            issues.append(f"{name}: duration 必須 > 0")
        if not bp.get("layers"):
            issues.append(f"{name}: 沒有任何圖層")
        for i, layer in enumerate(bp.get("layers", [])):
            ltype = layer.get("type")
            if ltype not in LAYER_TYPES:
                issues.append(f"{name}[{i}]: 未知圖層類型 {ltype}")
                continue
            preset = layer.get("preset")
            slot = layer.get("slot")
            if ltype == "particles":
                if slot:
                    ref = f"{slot}_{layer.get('style', name.split('_')[-1])}"
                    if ref not in PRESETS and slot not in PRESETS:
                        # slot 由槍皮風格在執行期解析；僅檢查槽位名稱合法性
                        if slot not in ("muzzle", "tracer", "impact", "kill", "smoke"):
                            issues.append(f"{name}[{i}]: 未知 slot {slot}")
                elif preset and preset not in PRESETS:
                    issues.append(f"{name}[{i}]: 未知粒子蓝图 {preset}")
            elif ltype == "decal" and preset and preset not in DECALS:
                issues.append(f"{name}[{i}]: 未知貼花 {preset}")
            elif ltype in ("sound",) :
                sfx = layer.get("sfx")
                if sfx and sfx not in SFX_REGISTRY:
                    issues.append(f"{name}[{i}]: 未知音效 {sfx}")
        audio = bp.get("audio") or {}
        sfx = audio.get("sfx")
        if sfx and sfx not in SFX_REGISTRY:
            issues.append(f"{name}.audio: 未知音效 {sfx}")
        mesh = [l for l in bp.get("layers", []) if l.get("type") == "mesh"]
        for l in mesh:
            if l.get("preset") not in MESH_PRIMITIVES:
                issues.append(f"{name}: 未知 mesh 元件 {l.get('preset')}")
    return issues
