"""
tools/skins/catalog.py — VANTA 槍皮目錄（唯一資料來源）
====================================================
一個「造型系列（collection）」包含多把武器的單品（skin），每個單品同時定義：

  * 色彩 / 材質（metalness、roughness、clearcoat、iridescence、發光強度）
  * 程序化花紋（pattern + 參數 → Godot/網頁共用同一套演算法）
  * 特效（砲口焰、曳光、命中、擊殺、彈殼、煙霧 —— 全部指向 VFX 蓝图名）
  * 升級等級（Radianite 解鎖：特效 / 塗裝 / 擊殺橫幅 / 槍飾 / 模型改裝）
  * 檢視動畫風格、音效變體、標籤與文案

客戶端（Godot）與展示台（Web）只讀本模組產出的 JSON，
任何地方都不重複硬編碼槍皮外觀 —— 這是「成熟專案」的關鍵紀律。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

# --------------------------------------------------------------------- #
# 分級（對齊《特戰英豪》的稀有度語彙）
# --------------------------------------------------------------------- #
TIERS: dict[str, dict[str, Any]] = {
    "standard": {"label": "原始本色", "label_en": "Standard Issue", "color": "#8f96a3",
                 "base_price": 0, "glow": 0.0},
    "select": {"label": "精選", "label_en": "Select", "color": "#5ad1a0",
               "base_price": 875, "glow": 0.25},
    "deluxe": {"label": "豪華", "label_en": "Deluxe", "color": "#5aa0f0",
               "base_price": 1425, "glow": 0.45},
    "premium": {"label": "尊貴", "label_en": "Premium", "color": "#b57df0",
                "base_price": 1775, "glow": 0.75},
    "ultra": {"label": "終極", "label_en": "Ultra", "color": "#f0c14b",
              "base_price": 2175, "glow": 1.0},
    "exclusive": {"label": "限定傳說", "label_en": "Exclusive", "color": "#ff5b7f",
                  "base_price": 2475, "glow": 1.25},
}

TIER_ORDER: tuple[str, ...] = ("standard", "select", "deluxe", "premium",
                               "ultra", "exclusive")

# 武器鍵（與 server/game/weapons.py 的 WeaponStats.key 一致）
WEAPONS: tuple[str, ...] = (
    "vandal", "phantom", "guardian", "spectre", "sheriff", "ghost",
    "classic", "operator", "ares", "knife",
)

WEAPON_LABELS: dict[str, str] = {
    "vandal": "暴徒 Vandal", "phantom": "幻象 Phantom", "guardian": "衛士 Guardian",
    "spectre": "幽影 Spectre", "sheriff": "警長 Sheriff", "ghost": "鬼魅 Ghost",
    "classic": "經典 Classic", "operator": "遊俠 Operator", "ares": "戰神 Ares",
    "knife": "匕首 Blade",
}

# 匕首造型加價（Valorant 的近戰皮一律比較貴）
KNIFE_PRICE_MULT = 1.6

# 舊版 Godot 客戶端以整數 weapon_id 索引（0=Phantom … 4=匕首）
# 保留對應表，讓升級過程不破壞既有場景。
LEGACY_WEAPON_ID: dict[str, int] = {
    "phantom": 0, "vandal": 1, "ghost": 2, "classic": 3, "knife": 4,
}


# --------------------------------------------------------------------- #
# 資料結構
# --------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Colorway:
    """一套配色＋材質參數（可作為主色板或 Chroma 變體）。"""

    name: str = "本質"
    primary: str = "#2b2f38"
    secondary: str = "#171a20"
    accent: str = "#ff7a35"
    emissive: str = "#ff9d4d"
    metalness: float = 0.55
    roughness: float = 0.38
    clearcoat: float = 0.0
    clearcoat_roughness: float = 0.25
    iridescence: float = 0.0
    anisotropy: float = 0.0
    pattern_mix: float = 0.45           # 花紋對 albedo 的調變強度
    emissive_strength: float = 1.0      # 發光倍率（Godot emission_energy）
    rim_color: str = "#ffffff"
    rim_strength: float = 0.0
    wear: float = 0.12                  # 邊緣磨損／氧化強度
    tint_variance: float = 0.05         # 逐零件色相微變，避免塑膠感

    def to_dict(self) -> dict:
        d = {"name": self.name, "primary": self.primary, "secondary": self.secondary,
             "accent": self.accent, "emissive": self.emissive,
             "metalness": round(self.metalness, 4), "roughness": round(self.roughness, 4),
             "clearcoat": round(self.clearcoat, 4),
             "clearcoat_roughness": round(self.clearcoat_roughness, 4),
             "iridescence": round(self.iridescence, 4),
             "anisotropy": round(self.anisotropy, 4),
             "pattern_mix": round(self.pattern_mix, 4),
             "emissive_strength": round(self.emissive_strength, 4),
             "rim_color": self.rim_color, "rim_strength": round(self.rim_strength, 4),
             "wear": round(self.wear, 4), "tint_variance": round(self.tint_variance, 4)}
        return d


@dataclass(frozen=True, slots=True)
class FxSpec:
    """特效綁定：指定「風格」即可，蓝图名稱自動解析（亦可單項覆寫）。

    風格 = tools/vfx/styles.py 的 12 套視覺語彙；每個風格提供
    muzzle_/tracer_/impact_/kill_/smoke_ 五種槽位蓝图。
    """

    style: str = "default"
    muzzle: str = "muzzle_flash"
    muzzle_color: str = "#ffd9a0"
    muzzle_scale: float = 1.0
    muzzle_shape: str = "star"          # star / ring / hex / flame / soul / glitch / petal
    light_energy: float = 6.0
    light_color: str = "#ffb060"
    tracer: str = "tracer"
    tracer_color: str = "#ffe6a0"
    tracer_width: float = 1.0
    tracer_style: str = "bolt"          # plain / bolt / laser / ribbon / comet
    impact: str = "spark"
    impact_color: str = "#ffcf8a"
    impact_style: str = "cone"          # cone / ring / shatter / dissolve
    decal: str = "bullet_hole"
    kill: str = "kill_confirm"
    kill_color: str = "#ffdd66"
    kill_style: str = "burst"           # burst / soul / ash / shatter / petal / circuit
    banner_frame: str = "default"       # HUD 擊殺橫幅外框樣式
    shell_color: str = "#c9a24a"
    shell_glow: float = 0.0
    smoke: str = "none"                 # none / dust / ember / void / steam / toxic / petals
    smoke_color: str = ""
    sound_key: str = ""                 # 空＝沿用武器基礎音效
    sound_pitch: float = 1.0
    sound_gain_db: float = 0.0

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


@dataclass(frozen=True, slots=True)
class UpgradeStep:
    """Radianite 升級階（對標 Weapon Level 1→4＋Exalted）。"""

    level: int
    name: str
    kind: str                           # vfx / finish / banner / charm / model / voice
    radianite: int
    desc: str = ""

    def to_dict(self) -> dict:
        return {"level": self.level, "name": self.name, "kind": self.kind,
                "radianite": self.radianite, "desc": self.desc}


@dataclass(frozen=True, slots=True)
class WeaponSkin:
    """一把槍的一個造型單品。"""

    id: str
    collection: str
    collection_name: str
    weapon: str
    name: str
    tier: str
    price_vp: int
    colorway: Colorway = field(default_factory=Colorway)
    chroma: tuple = ()
    fx: FxSpec = field(default_factory=FxSpec)
    pattern: str = "noise"
    pattern_params: dict = field(default_factory=dict)
    features: tuple = ()
    upgrades: tuple = ()
    extras: tuple = ()
    inspect: str = "standard"
    desc: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collection": self.collection,
            "collection_name": self.collection_name,
            "weapon": self.weapon,
            "weapon_label": WEAPON_LABELS.get(self.weapon, self.weapon),
            "legacy_weapon_id": LEGACY_WEAPON_ID.get(self.weapon, -1),
            "name": self.name,
            "tier": self.tier,
            "tier_label": TIERS[self.tier]["label"],
            "tier_color": TIERS[self.tier]["color"],
            "tier_glow": TIERS[self.tier]["glow"],
            "price_vp": self.price_vp,
            "colorway": self.colorway.to_dict(),
            "chroma": [c.to_dict() for c in self.chroma],
            "fx": self.fx.to_dict(),
            "pattern": self.pattern,
            "pattern_params": dict(self.pattern_params),
            "features": list(self.features),
            "extras": [dict(e) for e in self.extras],
            "upgrades": [u.to_dict() for u in self.upgrades],
            "inspect": self.inspect,
            "desc": self.desc,
        }


@dataclass(frozen=True, slots=True)
class SkinCollection:
    """造型系列（對標 Bundle）。"""

    id: str
    name: str
    name_en: str
    tier: str
    artist: str
    lore: str
    weapons: tuple = WEAPONS
    price_vp: int = 0
    release: str = "2026 EP01"
    tags: tuple = ()

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "name_en": self.name_en,
                "tier": self.tier, "tier_label": TIERS[self.tier]["label"],
                "tier_color": TIERS[self.tier]["color"], "glow": TIERS[self.tier]["glow"],
                "artist": self.artist, "lore": self.lore,
                "weapons": list(self.weapons), "price_vp": self.price_vp,
                "release": self.release, "tags": list(self.tags)}


# --------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------- #
def _cw(name: str, primary: str, secondary: str, accent: str, emissive: str, **kw) -> Colorway:
    base = Colorway(name=name, primary=primary, secondary=secondary,
                    accent=accent, emissive=emissive)
    return replace(base, **kw) if kw else base


def _fx(**kw) -> FxSpec:
    """由 style 展開五个槽位蓝图名（已被顯式指定的欄位不覆蓋）。"""
    from tools.vfx import styles

    style = kw.get("style", "default")
    if style not in styles.STYLE_PRESETS:
        style = "default"
        kw["style"] = "default"
    slots = styles.slots_for(style)
    slots["smoke"] = f"smoke_{style}"
    for slot, name in slots.items():
        kw.setdefault(slot, name)
    # 防呆：槽位若指向不存在的粒子預設（例如打錯字），退回 style 對應名稱，
    # 免得執行期才在 FxManager 裡靜默查不到、該特效整個不出現。
    from tools.vfx.particles import PRESETS as _P
    for slot in ("muzzle", "tracer", "impact", "kill", "smoke"):
        val = kw.get(slot, "")
        if val and val not in _P:
            fallback = slots.get(slot, "")
            kw[slot] = fallback if fallback in _P else ""
    return FxSpec(**kw)


def _ups(*items) -> tuple:
    """(名稱, 類型, 拉帝安特, 說明) → UpgradeStep 序列（level 從 2 起）。

    容錯：單一升級被寫成扁平 4-tuple 時自動包一層，避免資料格式坑掉整條管線。
    """
    if items and isinstance(items[0], str):
        items = (items,)
    return tuple(UpgradeStep(i, n, k, r, d)
                 for i, (n, k, r, d) in enumerate(items, start=2))


# --------------------------------------------------------------------- #
# 系列定義
# --------------------------------------------------------------------- #
_COLLECTION_DEFS: list[dict] = [
    {
        "collection": "standard", "name": "原始本色", "name_en": "Standard Issue",
        "tier": "standard", "artist": "VANTA 基準組", "tags": ("預設", "平衡基準"),
        "lore": "沒有花俏的塗裝，只有一把可靠的槍。真正的高手不需要發光。",
        "pattern": "carbon", "pattern_params": {"weave": 8}, "inspect": "standard",
        "cw": ("戰術灰", "#2b2f38", "#191c22", "#6f7684", "#000000",
               {"metalness": 0.42, "roughness": 0.62, "pattern_mix": 0.18,
                "emissive_strength": 0.0, "wear": 0.22, "tint_variance": 0.06}),
        "fx": {"style": "default", "muzzle_color": "#ffd9a0", "muzzle_shape": "star",
               "light_energy": 4.0, "tracer_color": "#ffe6a0",
               "tracer_style": "bolt", "kill_color": "#ffdd66"},
        "upgrades": (), "features": (),
        "skin_names": {"knife": "制式匕首", "vandal": "制式暴徒", "phantom": "制式幻象"},
    },
    {
        "collection": "reaver", "name": "掠奪者", "name_en": "Reaver",
        "tier": "ultra", "artist": "VANTA 概念組", "tags": ("靈魂", "哥德", "暗黑"),
        "lore": "黑鐵鑄成的容器，囚禁著被遺忘的獵手。每開一槍，就有靈魂被吸入。",
        "pattern": "cracks", "pattern_params": {"scale": 3.0, "sharp": 3.2, "glow": 0.62},
        "inspect": "summon",
        "cw": ("虛空黑鐵", "#150d1c", "#0a0610", "#8b30d8", "#c65cff",
               {"metalness": 0.78, "roughness": 0.30, "clearcoat": 0.35, "pattern_mix": 0.62,
                "emissive_strength": 2.1, "rim_color": "#a347ff", "rim_strength": 0.55,
                "wear": 0.30, "tint_variance": 0.08}),
        "chroma": (("血月", "#1d0a12", "#0c0409", "#e02a4a", "#ff5d7a",
                    {"emissive_strength": 2.4, "rim_color": "#ff3b5c"}),
                   ("聖灰", "#20242c", "#101218", "#66d9ff", "#a8f0ff",
                    {"emissive_strength": 1.8, "rim_color": "#7fe8ff"})),
        "fx": {"style": "soul", "muzzle_color": "#c65cff", "muzzle_shape": "soul",
               "muzzle_scale": 1.25, "light_energy": 8.0, "light_color": "#8b30d8",
               "tracer_color": "#b45cff", "tracer_style": "ribbon",
               "tracer_width": 1.15, "impact_color": "#a44bff",
               "impact_style": "shatter", "decal": "burn_hole", "kill_color": "#c65cff", "kill_style": "soul", "banner_frame": "reaver",
               "shell_color": "#3a2348", "shell_glow": 0.5,
               "sound_key": "reaver_shot", "sound_pitch": 0.88, "sound_gain_db": -1.5},
        "upgrades": (("能量裂縫特效", "vfx", 20, "砲口與曳光轉為靈魂紫，並加入拖尾"),
                     ("血月塗裝", "finish", 10, "可切換 Chroma 色板"),
                     ("噬魂擊殺橫幅", "banner", 20, "擊殺時浮現靈魂吸收動畫"),
                     ("墮落槍飾", "charm", 15, "懸掛的小頭骨，開槍時搖曳")),
        "features": ("energy_veins", "aura", "charm", "holo_sight"),
        "extras": ({"kind": "orb", "pos": (0.0, 0.09, 0.06), "size": 0.045,
                    "color": "emissive", "pulse": 1.6}),
    },
    {
        "collection": "prime", "name": "貴族", "name_en": "Prime",
        "tier": "premium", "artist": "VANTA 概念組", "tags": ("能量", "黑金", "經典"),
        "lore": "以凝固的恆星能量鍛造，開槍時核心會像呼吸一樣點燃。",
        "pattern": "hex", "pattern_params": {"cells": 9, "glow": 0.26}, "inspect": "charge",
        "cw": ("黑曜金芯", "#191a20", "#0e0f14", "#ffb020", "#ffd76a",
               {"metalness": 0.86, "roughness": 0.24, "clearcoat": 0.55, "pattern_mix": 0.42,
                "emissive_strength": 2.6, "rim_color": "#ffbb4d", "rim_strength": 0.4,
                "wear": 0.10}),
        "chroma": (("翡翠核心", "#12191a", "#080d0e", "#25e0a0", "#9dffd4",
                    {"emissive_strength": 2.3, "rim_color": "#3ff0b0"}),
                   ("蒼藍核心", "#101420", "#080b12", "#2fa8ff", "#a8dcff",
                    {"emissive_strength": 2.3, "rim_color": "#48b8ff"})),
        "fx": {"style": "energy", "muzzle_color": "#ffcf6a", "muzzle_shape": "ring",
               "muzzle_scale": 1.15, "light_energy": 7.0, "light_color": "#ffa32a",
               "tracer_color": "#ffbe55", "tracer_style": "comet",
               "impact_color": "#ffcb6a", "impact_style": "ring",
               "decal": "scorch_ring", "kill_color": "#ffd76a",
               "kill_style": "burst", "banner_frame": "prime", "shell_color": "#e0b25a",
               "shell_glow": 0.25, "sound_key": "prime_shot",
               "sound_pitch": 1.06},
        "upgrades": (("能量環特效", "vfx", 20, "命中產生擴散能量環"),
                     ("Chroma 色板", "finish", 10, "翡翠／蒼藍核心可切換"),
                     ("貴族槍口環", "model", 20, "槍口附加旋轉的能量環")),
        "features": ("energy_core", "holo_ring", "holo_sight"),
        "extras": ({"kind": "ring", "pos": (0.0, 0.0, -0.74), "size": 0.075,
                    "color": "emissive", "spin": 2.2}),
    },
    {
        "collection": "sentinels", "name": "光之哨兵", "name_en": "Sentinels of Light",
        "tier": "premium", "artist": "VANTA 概念組", "tags": ("聖光", "白藍", "傳說"),
        "lore": "眾神留下的守護之刃，光環在夜裡會自行點亮，替持槍者擋下恐懼。",
        "pattern": "marble", "pattern_params": {"scale": 1.6, "twist": 5.0},
        "inspect": "halo",
        "cw": ("聖白鎏金", "#e9edf4", "#b9c2d2", "#2f7cff", "#bfe0ff",
               {"metalness": 0.34, "roughness": 0.28, "clearcoat": 0.7, "pattern_mix": 0.30,
                "emissive_strength": 1.3, "iridescence": 0.35, "rim_color": "#cfe6ff",
                "rim_strength": 0.5, "wear": 0.06}),
        "fx": {"style": "holy", "muzzle_color": "#dff0ff", "muzzle_shape": "star",
               "muzzle_scale": 1.1, "light_energy": 6.5, "light_color": "#8fc4ff",
               "tracer_color": "#e8f4ff", "tracer_style": "laser",
               "impact_color": "#cfe6ff", "impact_style": "ring",
               "decal": "holy_mark", "kill_color": "#cbe4ff",
               "kill_style": "burst", "banner_frame": "sentinels", "shell_color": "#cfd6e2", "sound_key": "sentinels_shot", "sound_pitch": 1.02},
        "upgrades": (("聖光特效", "vfx", 20, "子彈拖出光翼，命中潑出聖光"),),
        "features": ("halo", "energy_veins"),
        "extras": ({"kind": "halo", "pos": (0.0, 0.13, -0.02), "size": 0.10,
                    "color": "accent", "spin": 0.8}),
    },
    {
        "collection": "dragontail", "name": "龍炎", "name_en": "Dragontail",
        "tier": "ultra", "artist": "VANTA 概念組", "tags": ("東方", "龍鱗", "吐息"),
        "lore": "龍脊上的鱗片被取下鑄成槍身，開火時是龍的一口吐息。",
        "pattern": "scales", "pattern_params": {"cells": 11, "bump": 1.15},
        "inspect": "dragon",
        "cw": ("赤鱗金爪", "#4a0d09", "#25060a", "#ffc23a", "#ff7a2a",
               {"metalness": 0.62, "roughness": 0.34, "clearcoat": 0.30, "pattern_mix": 0.80,
                "emissive_strength": 1.6, "rim_color": "#ff8a3a", "rim_strength": 0.35,
                "wear": 0.22, "tint_variance": 0.12}),
        "chroma": (("青鱗", "#07281f", "#04140f", "#8ce8c0", "#39f0a0",
                    {"emissive_strength": 1.9, "rim_color": "#4dffb8"}),
                   ("墨鱗", "#120f14", "#070609", "#9a7cff", "#c0aeff",
                    {"emissive_strength": 1.7, "rim_color": "#8f6cff"})),
        "fx": {"style": "dragon", "muzzle_color": "#ffb04d", "muzzle_shape": "flame",
               "muzzle_scale": 1.45, "light_energy": 9.0, "light_color": "#ff6a20",
               "tracer_color": "#ff9a3c", "tracer_style": "comet",
               "tracer_width": 1.35, "impact_color": "#ff8a3a",
               "impact_style": "cone", "decal": "burn_hole", "kill_color": "#ffb347", "kill_style": "ash", "banner_frame": "dragontail",
               "shell_color": "#d9a03c", "shell_glow": 0.4,
               "sound_key": "dragon_roar", "sound_pitch": 0.94, "sound_gain_db": -0.5},
        "upgrades": (("龍吐息特效", "vfx", 20, "砲口化為龍口噴焰，曳光帶火星"),
                     ("青鱗／墨鱗塗裝", "finish", 10, "兩套 Chroma 鱗色"),
                     ("龍魂擊殺特效", "banner", 20, "擊殺時浮現龍影嘶吼"),
                     ("逆鱗槍飾", "charm", 15, "會隨移動擺動的龍角")),
        "features": ("dragon_spine", "scale_wrap", "charm", "emissive_edge"),
        "extras": ({"kind": "spine", "pos": (0.0, 0.062, -0.10), "size": 0.03,
                    "color": "accent", "count": 7}),
    },
    {
        "collection": "elderflame", "name": "暗影龍焰", "name_en": "Elderflame",
        "tier": "exclusive", "artist": "VANTA 概念組", "tags": ("活體", "生長", "傳說"),
        "lore": "它不是被造出來的，是被養大的。餵它火，它給你勝利。",
        "pattern": "flame", "pattern_params": {"freq": 3.2, "seed": 29}, "inspect": "awaken",
        "cw": ("熔岩皮", "#260705", "#160303", "#ff5b18", "#ff9a3c",
               {"metalness": 0.28, "roughness": 0.52, "pattern_mix": 0.9,
                "emissive_strength": 2.8, "rim_color": "#ff5a20", "rim_strength": 0.7,
                "wear": 0.35, "tint_variance": 0.16}),
        "fx": {"style": "breath", "muzzle_color": "#ff7a2a", "muzzle_shape": "flame",
               "muzzle_scale": 1.6, "light_energy": 10.0, "light_color": "#ff5b18",
               "tracer_color": "#ff8a3a", "tracer_style": "comet",
               "tracer_width": 1.5, "impact_color": "#ff7a2a",
               "impact_style": "shatter", "decal": "melt_hole", "kill_color": "#ff9a3c", "kill_style": "ash", "banner_frame": "elderflame",
               "shell_color": "#ff7a2a", "shell_glow": 0.8,
               "sound_key": "elderflame_shot", "sound_pitch": 0.84, "sound_gain_db": -1.0},
        "upgrades": (("火焰呼吸", "vfx", 25, "開槍時皮質張開、噴出火星"),
                     ("蘇醒檢視", "model", 20, "按 Y 時槍身會睜開眼睛")),
        "features": ("living_skin", "emissive_edge", "claw_grip", "energy_veins"),
        "extras": ({"kind": "eye", "pos": (0.055, 0.03, 0.06), "size": 0.028,
                    "color": "emissive", "blink": 5.0}),
    },
    {
        "collection": "glitchpop", "name": "源計畫", "name_en": "Glitchpop",
        "tier": "ultra", "artist": "VANTA 概念組", "tags": ("賽博", "故障", "霓虹"),
        "lore": "從網路深處抓出來的武器，建模只完成一半，剩下的靠故障補上。",
        "pattern": "scanline", "pattern_params": {"lines": 42, "blocky": 0.65},
        "inspect": "glitch",
        "cw": ("霓虹故障", "#0b1420", "#050a12", "#00f5c8", "#ff2fb0",
               {"metalness": 0.50, "roughness": 0.22, "clearcoat": 0.80, "pattern_mix": 0.55,
                "emissive_strength": 2.9, "rim_color": "#00ffd0", "rim_strength": 0.6,
                "wear": 0.05, "anisotropy": 0.4}),
        "chroma": (("品紅主宰", "#150a1c", "#0a0410", "#ff2fb0", "#00f5c8",
                    {"emissive_strength": 3.0, "rim_color": "#ff4fc0"}),
                   ("電光黃", "#101608", "#060a04", "#d8ff2f", "#00f5c8",
                    {"emissive_strength": 2.6, "rim_color": "#e6ff5a"})),
        "fx": {"style": "glitch", "muzzle_color": "#00ffd0", "muzzle_shape": "glitch",
               "muzzle_scale": 1.2, "light_energy": 7.5, "light_color": "#00ffd0",
               "tracer_color": "#ff2fb0", "tracer_style": "bolt",
               "tracer_width": 1.2, "impact_color": "#00ffd0",
               "impact_style": "dissolve", "decal": "pixel_burn", "kill_color": "#ff2fb0", "kill_style": "circuit", "banner_frame": "glitchpop",
               "shell_color": "#12303a", "shell_glow": 0.6,
               "sound_key": "glitch_shot", "sound_pitch": 1.12, "sound_gain_db": -2.0},
        "upgrades": (("故障特效", "vfx", 20, "子彈與命中產生 RGB 分離故障"),
                     ("Chroma 色板", "finish", 10, "品紅／電光黃"),
                     ("錯誤擊殺橫幅", "banner", 20, "擊殺標記以故障字體崩解"),
                     ("資料溢位槍飾", "charm", 12, "漂浮的立方體，隨機位移")),
        "features": ("glitch_layers", "holo_sight", "charm", "energy_veins"),
        "extras": ({"kind": "shards", "pos": (-0.05, 0.07, -0.02), "size": 0.022,
                    "color": "emissive", "count": 5, "jitter": 0.4}),
    },
    {
        "collection": "ion", "name": "离子", "name_en": "Ion",
        "tier": "premium", "artist": "VANTA 概念組", "tags": ("未來", "全息", "雷射"),
        "lore": "軌道防衛軍的制式能量步槍，子彈早已退場，留下的是被加速的光。",
        "pattern": "circuit", "pattern_params": {"cells": 14, "width": 0.18},
        "inspect": "holo",
        "cw": ("白色軍規", "#dfe4ea", "#9aa4b0", "#ff8a2a", "#ffd08a",
               {"metalness": 0.55, "roughness": 0.30, "clearcoat": 0.45, "pattern_mix": 0.35,
                "emissive_strength": 2.2, "rim_color": "#ffc48a", "rim_strength": 0.3,
                "wear": 0.08}),
        "fx": {"style": "laser", "muzzle_color": "#ffd6a0", "muzzle_shape": "ring",
               "light_energy": 6.0, "light_color": "#ff9a4d",
               "tracer_color": "#ffb04d", "tracer_style": "laser",
               "tracer_width": 0.8, "impact_color": "#ffb04d",
               "impact_style": "ring", "decal": "melt_hole", "kill_color": "#ffd08a", "kill_style": "burst", "banner_frame": "ion",
               "shell_color": "#d0d6de", "sound_key": "laser_shot",
               "sound_pitch": 1.24, "sound_gain_db": -1.0},
        "upgrades": (("雷射彈道", "vfx", 20, "曳光改為細雷射＋命中過曝"),),
        "features": ("holo_sight", "energy_core", "scope_hologram"),
    },
    {
        "collection": "winterwunder", "name": "冰霜紀元", "name_en": "Winterwunder",
        "tier": "deluxe", "artist": "VANTA 概念組", "tags": ("冰雪", "節日", "結晶"),
        "lore": "結霜的槍膛會把每顆子彈凍成冰棱，命中時碎成一地雪花。",
        "pattern": "frost", "pattern_params": {"cells": 10}, "inspect": "frost",
        "cw": ("霜冰", "#c8e2f2", "#8fb6cf", "#4fc3ff", "#e8faff",
               {"metalness": 0.25, "roughness": 0.18, "clearcoat": 0.90, "pattern_mix": 0.50,
                "emissive_strength": 1.4, "iridescence": 0.50, "rim_color": "#bfe9ff",
                "rim_strength": 0.60, "wear": 0.04}),
        "fx": {"style": "frost", "muzzle_color": "#c8f0ff", "muzzle_shape": "hex",
               "light_energy": 5.5, "light_color": "#6fc8ff",
               "tracer_color": "#bfe9ff", "tracer_style": "bolt",
               "impact_color": "#bfe9ff", "impact_style": "shatter",
               "decal": "frost_crack", "kill_color": "#a8e4ff",
               "kill_style": "shatter", "banner_frame": "winter", "shell_color": "#a8c8da", "sound_key": "ice_shot", "sound_pitch": 1.18},
        "upgrades": (("冰裂特效", "vfx", 10, "命中結霜、擊殺碎冰"),),
        "features": ("ice_crystals", "frost_breath"),
        "extras": ({"kind": "crystal", "pos": (0.0, 0.06, -0.30), "size": 0.03,
                    "color": "accent", "count": 4}),
    },
    {
        "collection": "vipersbite", "name": "毒素之牙", "name_en": "Viper's Bite",
        "tier": "deluxe", "artist": "VANTA 概念組", "tags": ("毒液", "腐蝕", "生技"),
        "lore": "蛇牙造型的供彈機構，注入的不是火藥，是能溶解護甲的毒。",
        "pattern": "marble", "pattern_params": {"scale": 2.4, "twist": 9.0}, "inspect": "venom",
        "cw": ("毒囊綠", "#0c2412", "#061208", "#38ff7a", "#a8ff5c",
               {"metalness": 0.35, "roughness": 0.45, "clearcoat": 0.60, "pattern_mix": 0.70,
                "emissive_strength": 1.9, "rim_color": "#4dff8a", "rim_strength": 0.35,
                "wear": 0.25, "tint_variance": 0.10}),
        "fx": {"style": "venom", "muzzle_color": "#8aff4d", "muzzle_shape": "flame",
               "light_energy": 5.5, "light_color": "#3dff70",
               "tracer_color": "#a8ff5c", "tracer_style": "comet",
               "impact_color": "#8aff4d", "impact_style": "dissolve",
               "decal": "acid_burn", "kill_color": "#8aff4d",
               "kill_style": "dissolve", "banner_frame": "viper", "shell_color": "#2a4a2a",
               "shell_glow": 0.35, "sound_key": "venom_shot",
               "sound_pitch": 0.96},
        "upgrades": (("腐蝕特效", "vfx", 10, "命中滴落毒液、牆面被蝕穿"),),
        "features": ("venom_sac", "emissive_edge"),
    },
    {
        "collection": "nova", "name": "星塵", "name_en": "Nova",
        "tier": "select", "artist": "VANTA 概念組", "tags": ("宇宙", "低價", "入門"),
        "lore": "以隕石鐵鑄造，槍身裡還嵌著四十億年前的星屑。",
        "pattern": "nebula", "pattern_params": {"scale": 2.2, "stars": 70},
        "inspect": "standard",
        "cw": ("夜空星屑", "#130f26", "#0a0818", "#6a7dff", "#b8c4ff",
               {"metalness": 0.60, "roughness": 0.42, "pattern_mix": 0.62,
                "emissive_strength": 1.1, "rim_color": "#8ea0ff", "rim_strength": 0.20,
                "wear": 0.18}),
        "fx": {"style": "stardust", "muzzle_color": "#a8b8ff", "muzzle_shape": "star",
               "light_energy": 5.0, "light_color": "#6a7dff",
               "tracer_color": "#c0ccff", "tracer_style": "comet",
               "impact_color": "#a8b8ff", "impact_style": "cone",
               "kill_color": "#b8c4ff", "kill_style": "burst",
               "banner_frame": "nova", "shell_color": "#3a3660"},
        "upgrades": (), "features": ("star_field",),
    },
    {
        "collection": "higanbana", "name": "彼岸花", "name_en": "Kunohei",
        "tier": "premium", "artist": "VANTA 概念組", "tags": ("東方", "武士", "落櫻"),
        "lore": "刀匠把斷刀的碎片埋進墳場，第二年春天開滿了彼岸花。",
        "pattern": "sakura", "pattern_params": {"count": 26, "seed": 41}, "inspect": "draw",
        "cw": ("白鞘朱刃", "#efe6e2", "#c9bcb6", "#d81f3a", "#ff7a90",
               {"metalness": 0.70, "roughness": 0.22, "clearcoat": 0.50, "pattern_mix": 0.42,
                "emissive_strength": 1.0, "rim_color": "#ff9aa8", "rim_strength": 0.25,
                "wear": 0.14}),
        "fx": {"style": "petal", "muzzle_color": "#ffd6de", "muzzle_shape": "petal",
               "light_energy": 5.0, "light_color": "#ff6a80",
               "tracer_color": "#ffb0c0", "tracer_style": "ribbon",
               "impact_color": "#ff9aa8", "impact_style": "cone",
               "kill_color": "#ff5a76", "kill_style": "petal",
               "banner_frame": "sakura", "shell_color": "#d8c8c0",
               "sound_key": "katana_swing", "sound_pitch": 1.05},
        "upgrades": (("落花特效", "vfx", 20, "擊殺時花瓣飛散"),),
        "features": ("wrap_grip", "tassel_charm", "blade_glow"),
        "extras": ({"kind": "tassel", "pos": (0.0, -0.02, 0.16), "size": 0.02,
                    "color": "accent", "sway": 1.4}),
    },
    {
        "collection": "araxys", "name": "熔核", "name_en": "Araxys",
        "tier": "premium", "artist": "VANTA 概念組", "tags": ("隕石", "黑金", "熔漿"),
        "lore": "從地核深處撈出來的金屬，冷卻後仍是熾熱的黑色。",
        "pattern": "cracks", "pattern_params": {"scale": 2.4, "sharp": 4.0, "glow": 0.8},
        "inspect": "charge",
        "cw": ("隕鐵黑", "#121113", "#080809", "#ff4a1a", "#ffb04d",
               {"metalness": 0.90, "roughness": 0.28, "pattern_mix": 0.70,
                "emissive_strength": 2.4, "rim_color": "#ff6a2a", "rim_strength": 0.45,
                "wear": 0.28}),
        "fx": {"style": "magma", "muzzle_color": "#ff8a3a", "muzzle_shape": "hex",
               "light_energy": 8.5, "light_color": "#ff5a1a",
               "tracer_color": "#ff7a2a", "tracer_style": "comet",
               "impact_color": "#ff8a3a", "impact_style": "shatter",
               "decal": "melt_hole", "kill_color": "#ffb04d",
               "kill_style": "burst", "banner_frame": "araxys", "shell_color": "#2a1a14",
               "shell_glow": 0.7, "sound_key": "araxys_shot",
               "sound_pitch": 0.92},
        "upgrades": (("熔核噴流", "vfx", 20, "命中濺出熔岩碎塊"),),
        "features": ("energy_veins", "molten_cracks"),
    },
    {
        "collection": "tactical", "name": "戰術軍規", "name_en": "Field Ops",
        "tier": "select", "artist": "VANTA 概念組", "tags": ("軍事", "迷彩", "務實"),
        "lore": "沒有發光元件、沒有動畫，只有防滑紋與消光塗層——老玩家的選擇。",
        "pattern": "camo", "pattern_params": {"blobs": 16, "seed": 44}, "inspect": "standard",
        "cw": ("橄欖沙色", "#39402c", "#22261b", "#c9b48a", "#c9b48a",
               {"metalness": 0.20, "roughness": 0.78, "pattern_mix": 0.55,
                "emissive_strength": 0.0, "rim_color": "#8a9070", "rim_strength": 0.0,
                "wear": 0.45, "tint_variance": 0.10}),
        "fx": {"style": "default", "muzzle_color": "#ffe0b0", "muzzle_shape": "star",
               "light_energy": 4.5, "tracer_color": "#ffe6a0", "tracer_style": "bolt",
               "impact_color": "#ffd0a0", "kill_color": "#ffe0a0",
               "shell_color": "#b99a4a"},
        "upgrades": (), "features": ("rail_slots", "grip_texture", "tracer_pack"),
    },
]

# 每個系列的「武器特化」覆寫：讓同一系列在不同槍上真的長得不一樣
_WEAPON_SHAPE: dict[str, dict] = {
    "knife": {"price_mult": KNIFE_PRICE_MULT, "features": ("blade_aura",)},
    "operator": {"price_mult": 1.15, "features": ("long_barrel", "scope")},
    "vandal": {"price_mult": 1.0, "features": ("rifle",)},
    "phantom": {"price_mult": 1.0, "features": ("rifle", "suppressor")},
    "guardian": {"price_mult": 0.9, "features": ("rifle",)},
    "spectre": {"price_mult": 0.8, "features": ("smg",)},
    "ares": {"price_mult": 1.1, "features": ("lmg", "belt_feed")},
    "sheriff": {"price_mult": 0.85, "features": ("revolver_frame",)},
    "ghost": {"price_mult": 0.8, "features": ("pistol", "suppressor")},
    "classic": {"price_mult": 0.7, "features": ("pistol",)},
}


# --------------------------------------------------------------------- #
# 展開：系列定義 → 單品清單
# --------------------------------------------------------------------- #
def _price_for(tier: str, weapon: str) -> int:
    """造型價格：依稀有度基準 × 武器類型倍率，取整到 25 VP（Valorant 習慣）。"""
    base = TIERS[tier]["base_price"]
    if base <= 0:
        return 0
    mult = float(_WEAPON_SHAPE.get(weapon, {}).get("price_mult", 1.0))
    return max(25, int(round(base * mult / 25.0)) * 25)


def _skin_name(coll_name: str, weapon: str) -> str:
    label = WEAPON_LABELS.get(weapon, weapon)
    return f"{coll_name} {label}"


def build_catalog() -> tuple[list[SkinCollection], list[WeaponSkin]]:
    """由系列定義展開（確定性；同一份資料 → 同一份輸出）。"""
    collections: list[SkinCollection] = []
    skins: list[WeaponSkin] = []
    for d in _COLLECTION_DEFS:
        weapons = tuple(d.get("weapons", WEAPONS))
        tier = d["tier"]
        total = 0
        for w in weapons:
            total += _price_for(tier, w)
        coll = SkinCollection(id=d["collection"], name=d["name"], name_en=d["name_en"],
                              tier=tier, artist=d["artist"], lore=d["lore"],
                              weapons=weapons,
                              price_vp=int(round(total * 0.9 / 25.0)) * 25,   # 整套 10% OFF
                              tags=d.get("tags", ()))
        collections.append(coll)

        cw_args, cw_kw = d["cw"][0:5], d["cw"][5] if len(d["cw"]) > 5 else {}
        base_cw = _cw(*cw_args, **cw_kw)
        chroma = tuple(_cw(*c[:5], **(c[5] if len(c) > 5 else {})) for c in d.get("chroma", ()))
        fx = _fx(**d.get("fx", {}))
        ups = _ups(*d.get("upgrades", ()))
        raw_extras = d.get("extras", ())
        if isinstance(raw_extras, dict):      # 單一裝飾件常被写成 ( {...} ) — 實際是 dict
            raw_extras = (raw_extras,)
        extras = tuple(raw_extras)
        for w in weapons:
            shape = _WEAPON_SHAPE.get(w, {})
            feats = tuple(dict.fromkeys(tuple(d.get("features", ())) +
                                         tuple(shape.get("features", ()))))
            skin_id = f"{coll.id}_{w}"
            name = d.get("skin_names", {}).get(w) or _skin_name(coll.name, w)
            skins.append(WeaponSkin(
                id=skin_id, collection=coll.id, collection_name=coll.name, weapon=w,
                name=name, tier=tier, price_vp=_price_for(tier, w), colorway=base_cw,
                chroma=chroma, fx=fx, pattern=d["pattern"],
                pattern_params=d.get("pattern_params", {}), features=feats,
                upgrades=ups,
                extras=extras, inspect=d.get("inspect", "standard"),
                desc=d["lore"],
            ))
    return collections, skins


COLLECTIONS: list[SkinCollection] = []
SKINS: list[WeaponSkin] = []
_BY_ID: dict[str, WeaponSkin] = {}


def _ensure_built() -> None:
    global COLLECTIONS, SKINS, _BY_ID
    if not SKINS:
        COLLECTIONS, SKINS = build_catalog()
        _BY_ID = {s.id: s for s in SKINS}


def skin_by_id(skin_id: str) -> WeaponSkin | None:
    _ensure_built()
    return _BY_ID.get(skin_id)


def skins_for_weapon(weapon: str, owned_only: set[str] | None = None) -> list[WeaponSkin]:
    _ensure_built()
    out = [s for s in SKINS if s.weapon == weapon]
    if owned_only is not None:
        out = [s for s in out if s.id in owned_only]
    return sorted(out, key=lambda s: (-TIER_ORDER.index(s.tier), s.collection))


def collections() -> list[SkinCollection]:
    _ensure_built()
    return list(COLLECTIONS)


def collect() -> dict:
    """完整目錄 dict（供 write_json / 客戶端載入）。"""
    _ensure_built()
    from tools.vfx.blueprints import BLUEPRINTS, MESH_PRIMITIVES
    from tools.vfx.decals import DECALS
    from tools.vfx.particles import PRESETS, to_dict as emitter_to_dict
    from tools.vfx.sprites import SPRITES
    from tools.vfx.styles import STYLE_META, STYLE_PRESETS
    from tools.skins.emit import texture_spec

    textures = {
        "particles": {k: emitter_to_dict(v) for k, v in sorted(PRESETS.items())},
        "sprites": {k: SPRITES[k] for k in sorted(SPRITES)},
        "decals": {k: DECALS[k] for k in sorted(DECALS)},
        "blueprints": {k: BLUEPRINTS[k] for k in sorted(BLUEPRINTS)},
        "mesh_primitives": MESH_PRIMITIVES,
        "styles": {k: list(v) for k, v in sorted(STYLE_PRESETS.items())},
        "style_meta": STYLE_META,
    }
    return {
        "version": 2,
        "tiers": TIERS,
        "tier_order": list(TIER_ORDER),
        "weapons": list(WEAPONS),
        "weapon_labels": WEAPON_LABELS,
        "collections": [c.to_dict() for c in COLLECTIONS],
        "skins": [s.to_dict() for s in SKINS],
        "stats": {"collections": len(COLLECTIONS), "skins": len(SKINS)},
        "texture_spec": texture_spec(),
        "effects": textures,
    }


# --------------------------------------------------------------------- #
# 驗證（工具鏈與測試共用；确保資料不會「看起來對但玩起來壞」）
# --------------------------------------------------------------------- #
def validate_catalog() -> list[str]:
    """回傳問題清單（空＝通過）。"""
    from server.game.weapons import WEAPONS as SERVER_WEAPONS
    from tools.vfx.particles import PRESETS as PARTICLE_PRESETS

    _ensure_built()
    issues: list[str] = []
    seen: set[str] = set()
    for s in SKINS:
        if s.id in seen:
            issues.append(f"重複 skin id: {s.id}")
        seen.add(s.id)
        if s.weapon not in WEAPONS:
            issues.append(f"{s.id}: 未知武器 {s.weapon}")
        elif s.weapon not in SERVER_WEAPONS:
            issues.append(f"{s.id}: 武器不存在於伺服器資料庫 {s.weapon}")
        if s.tier not in TIERS:
            issues.append(f"{s.id}: 未知稀有度 {s.tier}")
        if s.price_vp < 0:
            issues.append(f"{s.id}: 負價 {s.price_vp}")
        if s.tier != "standard" and s.price_vp <= 0:
            issues.append(f"{s.id}: 非預設造型必須有價格")
        for key, color in (("primary", s.colorway.primary), ("secondary", s.colorway.secondary),
                           ("accent", s.colorway.accent), ("emissive", s.colorway.emissive),
                           ("rim", s.colorway.rim_color)):
            if not _is_hex(color):
                issues.append(f"{s.id}: 非法顏色 {key}={color}")
        for p in ("metalness", "roughness", "clearcoat", "iridescence", "pattern_mix",
                  "rim_strength", "wear", "tint_variance"):
            v = getattr(s.colorway, p)
            if not 0.0 <= v <= 1.0:
                issues.append(f"{s.id}: {p}={v} 超出 0..1")
        if not 0.0 <= s.colorway.emissive_strength <= 6.0:
            issues.append(f"{s.id}: emissive_strength 超出 0..6")
        for fname in ("muzzle", "tracer", "impact", "kill", "smoke"):
            fx_name = getattr(s.fx, fname)
            if fx_name and fx_name not in PARTICLE_PRESETS:
                issues.append(f"{s.id}: fx.{fname} 引用不存在的粒子預設 {fx_name}")
        for c in s.chroma:
            if not _is_hex(c.primary):
                issues.append(f"{s.id}: Chroma 非法顏色")
        for u in s.upgrades:
            if u.level < 2 or u.radianite < 0:
                issues.append(f"{s.id}: 升級階 illegal L{u.level}/{u.radianite}")
            if u.kind not in ("vfx", "finish", "banner", "charm", "model", "voice"):
                issues.append(f"{s.id}: 未知升級類型 {u.kind}")
        if s.pattern not in _known_patterns():
            issues.append(f"{s.id}: 未知花紋 {s.pattern}")
    for c in COLLECTIONS:
        if c.tier not in TIERS:
            issues.append(f"collection {c.id}: 未知稀有度")
        if not c.weapons:
            issues.append(f"collection {c.id}: 沒有武器")
    return issues


def _is_hex(color: str) -> bool:
    return (isinstance(color, str) and len(color) == 7 and color.startswith("#")
            and all(ch in "0123456789abcdefABCDEF" for ch in color[1:]))


def _known_patterns() -> set[str]:
    from tools.skins.patterns import PATTERNS
    return set(PATTERNS)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: tuple, b: tuple, t: float) -> tuple:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(rgb: tuple, factor: float) -> tuple:
    return tuple(min(255, max(0, int(round(v * factor)))) for v in rgb)
