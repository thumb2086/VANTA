"""
tools/weapons/modular.py — 槍械模組化系統
==========================================
把一把槍拆成「接收器 (WeaponFrame) + 模組 (Mod)」：
  * WeaponFrame：基礎數值（WeaponStats）+ 支援的模組槽位
  * Mod：單一改裝件，以「統計修正 dict」描述效果
  * ModdableWeapon：frame + mods → 計算最終數值，可轉換為
    server.game.weapons.WeaponStats（**直接進遊戲**）

修正規則（effects dict）：
  * "<stat>_mult" → 乘算（如 damage_mult=1.1 → 傷害 ×1.1）
  * "<stat>_add"  → 加算（如 mag_add=10 → 彈匣 +10）
  * "price_add"   → 價格加成
統計鍵：damage / fire_rate / mag / reload / spread / first_shot_accuracy /
        recoil / pen / ads_spread / move_speed / pellets
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.game.weapons import DamageFalloff, WeaponStats

# 模組可改的統計清單（用於驗證）
MODIFIABLE_STATS = (
    "damage", "fire_rate", "mag", "reload", "spread",
    "first_shot_accuracy", "recoil", "pen", "ads_spread",
    "move_speed", "pellets", "price",
)

SLOTS = ("receiver", "barrel", "muzzle", "mag", "grip", "sight", "stock")


@dataclass(frozen=True, slots=True)
class Mod:
    id: str
    name: str
    slot: str                      # 安裝槽位（見 SLOTS）
    price: int
    effects: dict                  # 統計修正 dict
    desc: str = ""

    def __post_init__(self) -> None:
        if self.slot not in SLOTS:
            raise ValueError(f"invalid slot: {self.slot}")
        for k in self.effects:
            base = k.removesuffix("_mult").removesuffix("_add")
            if base not in MODIFIABLE_STATS:
                raise ValueError(f"unknown stat modifier: {k}")


@dataclass(frozen=True, slots=True)
class WeaponFrame:
    key: str                       # 接收器 id（如 "vandal"）
    name: str
    base: WeaponStats              # 基礎武器數值
    slots: tuple = ("barrel", "mag", "grip", "sight", "stock", "muzzle")


class ModdableWeapon:
    """接收器 + 已安裝模組。"""

    def __init__(self, frame: WeaponFrame, mods: dict[str, Mod] | None = None):
        self.frame = frame
        self.mods: dict[str, Mod] = {}          # slot -> Mod（每槽最多一個）
        if mods:
            for slot, mod in mods.items():
                self.install(slot, mod)

    def install(self, slot: str, mod: Mod) -> bool:
        """安裝模組（槽位需相容且未被佔用）。回傳是否成功。"""
        if slot not in self.frame.slots or mod.slot != slot:
            return False
        self.mods[slot] = mod
        return True

    def uninstall(self, slot: str) -> Mod | None:
        return self.mods.pop(slot, None)

    # ------------------------------------------------------------------ #
    def _computed(self, stat: str, mult_key: str, add_key: str, base_value: float) -> float:
        """計算統計值 = (base × Π mult) + Σ add。"""
        mult, add = 1.0, 0.0
        for mod in self.mods.values():
            mult *= mod.effects.get(mult_key, 1.0)
            add += mod.effects.get(add_key, 0.0)
        return max(0.0, base_value * mult + add)

    def price(self) -> int:
        return int(self._computed("price", "price_mult", "price_add", self.frame.base.price))

    def stats(self) -> WeaponStats:
        b = self.frame.base
        return WeaponStats(
            key=f"{self.frame.key}_{self._slug()}",
            name=f"{self.frame.name} {self._suffix()}",
            wclass=b.wclass,
            price=self.price(),
            fire_rate_rps=self._computed("fire_rate", "fire_rate_mult", "fire_rate_add", b.fire_rate_rps),
            mag_size=int(self._computed("mag", "mag_mult", "mag_add", b.mag_size)),
            reserve=b.reserve,
            reload_time=self._computed("reload", "reload_mult", "reload_add", b.reload_time),
            damage=self._computed("damage", "damage_mult", "damage_add", b.damage),
            falloff=b.falloff,
            penetration_level=int(self._computed("pen", "pen_mult", "pen_add", b.penetration_level)),
            first_shot_accuracy=self._computed("first_shot_accuracy", "first_shot_accuracy_mult", "first_shot_accuracy_add", b.first_shot_accuracy),
            spread_per_bullet=self._computed("spread", "spread_mult", "spread_add", b.spread_per_bullet),
            move_speed_mult=self._computed("move_speed", "move_speed_mult", "move_speed_add", b.move_speed_mult),
            ads_spread_mult=self._computed("ads_spread", "ads_spread_mult", "ads_spread_add", b.ads_spread_mult),
            automatic=b.automatic,
            burst=b.burst,
            pellets=int(self._computed("pellets", "pellets_mult", "pellets_add", b.pellets)),
            scoped=b.scoped,
        )

    # ------------------------------------------------------------------ #
    def _slug(self) -> str:
        parts = sorted(self.mods.keys())
        return "-".join(parts) if parts else "base"

    def _suffix(self) -> str:
        names = sorted((mod.name for mod in self.mods.values()), key=lambda n: n)
        return "·" + "+".join(names[:3]) if names else ""

    def summary(self) -> dict:
        """除錯/匯出用：列出所有數值與安裝的模組。"""
        from dataclasses import asdict

        return {
            "frame": self.frame.key,
            "name": self.stats().name,
            "price": self.price(),
            "mods": {slot: mod.id for slot, mod in sorted(self.mods.items())},
            "stats": asdict(self.stats()),
        }


# --------------------------------------------------------------------- #
# 模組池（生成器共用）
# --------------------------------------------------------------------- #
MOD_POOL: dict[str, list[Mod]] = {
    "barrel": [
        Mod("long_barrel", "長槍管", "barrel", 900, {"damage_mult": 1.08, "fire_rate_mult": 0.94, "spread_mult": 0.9}),
        Mod("short_barrel", "短槍管", "barrel", 600, {"fire_rate_mult": 1.06, "spread_add": 0.008, "damage_mult": 0.96}),
        Mod("heavy_barrel", "重槍管", "barrel", 1200, {"recoil_mult": 0.8, "spread_mult": 0.85, "move_speed_mult": 0.96}),
    ],
    "muzzle": [
        Mod("compensator", "補償器", "muzzle", 700, {"recoil_mult": 0.85, "spread_mult": 0.95}),
        Mod("suppressor", "消音器", "muzzle", 800, {"spread_mult": 0.92, "damage_mult": 0.97, "recoil_mult": 0.9}),
        Mod("flash_hider", "防火帽", "muzzle", 400, {"recoil_mult": 0.92, "first_shot_accuracy_mult": 0.9}),
    ],
    "mag": [
        Mod("extended_mag", "加長彈匣", "mag", 500, {"mag_add": 10, "reload_mult": 1.15}),
        Mod("quick_mag", "快拔彈匣", "mag", 450, {"reload_mult": 0.75}),
        Mod("drum_mag", "彈鼓", "mag", 900, {"mag_add": 22, "reload_mult": 1.3, "move_speed_mult": 0.97}),
    ],
    "grip": [
        Mod("vertical_grip", "垂直握把", "grip", 650, {"recoil_mult": 0.82}),
        Mod("angled_grip", "斜角握把", "grip", 550, {"spread_mult": 0.9, "recoil_mult": 0.95}),
    ],
    "sight": [
        Mod("holo_sight", "全息瞄具", "sight", 750, {"first_shot_accuracy_mult": 0.85, "ads_spread_mult": 0.9}),
        Mod("red_dot", "紅點瞄具", "sight", 400, {"first_shot_accuracy_mult": 0.92}),
        Mod("scope_2x", "2x 瞄準鏡", "sight", 1100, {"first_shot_accuracy_mult": 0.7, "spread_mult": 0.85, "fire_rate_mult": 0.92, "move_speed_mult": 0.95}),
    ],
    "stock": [
        Mod("heavy_stock", "重型槍托", "stock", 550, {"recoil_mult": 0.88, "move_speed_mult": 0.96}),
        Mod("light_stock", "輕量槍托", "stock", 450, {"move_speed_mult": 1.05, "recoil_mult": 1.08}),
    ],
}


# 可模組化的接收器框架（從既有武器庫建構）
def frame_from_weapon(key: str, slots: tuple = ("barrel", "muzzle", "mag", "grip", "sight", "stock")) -> WeaponFrame:
    from server.game.weapons import weapon

    return WeaponFrame(key=key, name=weapon(key).name, base=weapon(key), slots=slots)
