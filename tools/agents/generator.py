"""
tools/agents/generator.py — 可程式化人物（角色）產生器
======================================================
以 seed 產生完整角色定義：
  * 身分：代號（唯一）、本名、代稱、陣營、簡介（模板組裝）
  * 角色定位：duelist / controller / sentinel / initiator（含定位描述、速度倍率）
  * 技能組：由技能池（flash/frag/smoke/trap/stim/heal）依定位模板組合
  * 配色：seed 驅動的主色/強調色/背景 → 供肖像與 UI 使用
  * 數值：生命、速度倍率、護甲偏好（元資料，供後續 bot/平衡使用）

角色可直接進遊戲：register_agent(def) → Player(agent_key=key) 即可使用。
確定性：所有決策由注入種子的 RNG 驅動。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from server.game.abilities import GENERATED_AGENTS, build_ability

# 技能池（遊戲內實際存在）
KNOWN_ABILITIES = ("flash", "frag", "smoke", "trap", "stim", "heal")

# 角色定位模板
ROLES: dict[str, dict] = {
    "duelist": dict(
        label="決鬥者", desc="先鋒突破，單兵作戰的尖刀",
        speed_mult=1.03, shield_pref="light", glyph="flash",
        kits=[["flash", "stim", "frag"], ["stim", "flash", "frag"], ["flash", "stim", "stim"]],
    ),
    "controller": dict(
        label="控場者", desc="以煙霧與封鎖主宰戰場節奏",
        speed_mult=0.99, shield_pref="heavy", glyph="smoke",
        kits=[["smoke", "smoke", "frag"], ["smoke", "trap", "smoke"]],
    ),
    "sentinel": dict(
        label="哨衛", desc="陣地防守與關鍵時刻的後盾",
        speed_mult=0.98, shield_pref="heavy", glyph="trap",
        kits=[["trap", "heal", "smoke"], ["heal", "trap", "frag"], ["trap", "heal", "stim"]],
    ),
    "initiator": dict(
        label="先鋒", desc="情報壓制與開戰的發動機",
        speed_mult=1.0, shield_pref="light", glyph="spark",
        kits=[["flash", "frag", "stim"], ["frag", "flash", "smoke"], ["flash", "stim", "trap"]],
    ),
}

# 代號零件池（可無限組合，批內唯一）
CODENAME_PRE = [
    "Nyx", "Vex", "Onyx", "Kai", "Nova", "Zephyr", "Umbra", "Ion", "Volt",
    "Hex", "Rune", "Blitz", "Ember", "Talon", "Frost", "Ash", "Vega", "Orion",
    "Jinx", "Reap", "Cinder", "Rogue", "Havoc", "Pulse", "Shade", "Vortex",
]
CODENAME_SUF = ["on", "is", "ara", "ix", "or", "yn", "eth", "us", "el", "ar"]

FIRST_NAMES = ["Mira", "Kai", "Dara", "Sorin", "Elena", "Ravi", "Noor", "Tomas", "Ivy", "Omar"]
LAST_NAMES = ["Chen", "Volkov", "Nguyen", "Kovac", "Adebayo", "Silva", "Tanaka", "Moreau", "Haddad", "Rossi"]
FACTIONS = ["ASGARD-9", "VANGUARD", "NIGHTFALL", "TEMPEST", "IRONFANG", "SHADOWLINE"]

TRAITS = [
    "以快狠準聞名", "沉默寡言但戰術精準", "戰場上從不退縮",
    "擅長聲東擊西", "總能在絕境冷靜收尾", "對隊友絕對忠誠",
    "信奉先發制人", "善用環境與掩體", "行動如幽靈般無聲",
]


@dataclass(slots=True)
class AgentDef:
    key: str
    codename: str
    name: str
    faction: str
    role: str
    role_label: str
    desc: str
    bio: str
    kit: list
    stats: dict
    colors: dict
    seed: int

    def to_dict(self) -> dict:
        return {
            "key": self.key, "codename": self.codename, "name": self.name,
            "faction": self.faction, "role": self.role, "role_label": self.role_label,
            "desc": self.desc, "bio": self.bio, "kit": list(self.kit),
            "stats": dict(self.stats), "colors": dict(self.colors), "seed": self.seed,
        }


# --------------------------------------------------------------------- #
# 配色（seed 驅動）
# --------------------------------------------------------------------- #
def hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    c = (1.0 - abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - abs((h / 60.0) % 2.0 - 1.0))
    m = l - c / 2.0
    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def make_palette(seed: int) -> dict:
    rng = random.Random(seed * 7919)
    hue = rng.uniform(0.0, 360.0)
    primary = hsl_to_rgb(hue, 0.75, 0.55)
    accent = hsl_to_rgb((hue + 45.0) % 360.0, 0.85, 0.62)
    bg1 = hsl_to_rgb(hue, 0.45, 0.16)
    bg2 = hsl_to_rgb((hue + 180.0) % 360.0, 0.5, 0.08)
    return {
        "primary": "#%02x%02x%02x" % primary,
        "accent": "#%02x%02x%02x" % accent,
        "bg1": "#%02x%02x%02x" % bg1,
        "bg2": "#%02x%02x%02x" % bg2,
    }


# --------------------------------------------------------------------- #
# 產生器
# --------------------------------------------------------------------- #
def _unique_codename(rng: random.Random, used: set[str]) -> str:
    for _ in range(200):
        cand = rng.choice(CODENAME_PRE) + rng.choice(CODENAME_SUF)
        if cand not in used:
            used.add(cand)
            return cand
    # 後備：加數字前綴保證唯一
    i = 0
    while True:
        cand = f"{rng.choice(CODENAME_PRE)}{i}"
        if cand not in used:
            used.add(cand)
            return cand
        i += 1


def generate_agent(seed: int, role: str | None = None, used: set[str] | None = None) -> AgentDef:
    """依 seed 產生一名角色。role 為 None 時隨機。"""
    rng = random.Random(seed)
    used = used if used is not None else set()
    if role is None or role not in ROLES:
        role = rng.choice(sorted(ROLES))
    tpl = ROLES[role]

    codename = _unique_codename(rng, used)
    key = codename.lower()
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    faction = rng.choice(FACTIONS)
    kit = list(rng.choice(tpl["kits"]))
    stats = {
        "hp": 100,
        "speed_mult": tpl["speed_mult"],
        "shield_pref": tpl["shield_pref"],
        "role_glyph": tpl["glyph"],
    }
    bio = f"{tpl['desc']}。{rng.choice(TRAITS)}。代號「{codename}」，隸屬 {faction}。"
    return AgentDef(
        key=key, codename=codename, name=name, faction=faction,
        role=role, role_label=tpl["label"], desc=tpl["desc"], bio=bio,
        kit=kit, stats=stats, colors=make_palette(seed), seed=seed,
    )


def generate_batch(seed: int = 100, count: int = 8) -> list[AgentDef]:
    """產生一批角色（代號唯一，seed 遞增）。"""
    used: set[str] = set()
    out = []
    for i in range(count):
        out.append(generate_agent(seed + i * 31, used=used))
    return out


# --------------------------------------------------------------------- #
# 驗證
# --------------------------------------------------------------------- #
def validate_agent(d: dict) -> list[str]:
    """結構驗證：必填欄位、技能池、數值範圍。回傳問題清單。"""
    issues = []
    for k in ("key", "codename", "name", "role", "kit", "stats", "colors", "bio"):
        if k not in d:
            issues.append(f"缺少欄位: {k}")
    if "kit" in d:
        for ab in d["kit"]:
            if ab not in KNOWN_ABILITIES:
                issues.append(f"未知技能: {ab}")
    st = d.get("stats", {})
    if "hp" in st and st["hp"] != 100:
        issues.append(f"hp 應為 100: {st['hp']}")
    if "speed_mult" in st and not (0.9 <= st["speed_mult"] <= 1.1):
        issues.append(f"speed_mult 超出範圍: {st['speed_mult']}")
    if "role" in d and d["role"] not in ROLES:
        issues.append(f"未知定位: {d['role']}")
    if "colors" in d:
        for k in ("primary", "accent", "bg1", "bg2"):
            if k not in d["colors"] or not str(d["colors"][k]).startswith("#"):
                issues.append(f"配色格式錯誤: {k}")
    return issues


# --------------------------------------------------------------------- #
# 註冊進遊戲
# --------------------------------------------------------------------- #
def register_agent(agent: AgentDef) -> str:
    """將角色註冊進遊戲（Player(agent_key=key) 即可使用）。回傳 key。"""
    kit = [build_ability(name) for name in agent.kit]
    GENERATED_AGENTS[agent.key] = (agent.codename, kit)
    return agent.key
