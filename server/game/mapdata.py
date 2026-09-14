"""
server/game/mapdata.py — 地圖資料（M14 最小版本）
=================================================
牆面以 AABB + 材質表示；材質決定「可否穿透」與「穿透衰減」。
視線判定 (LOS) 供煙霧/爆炸/閃光共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.core.math_core import Vec3
from server.game.geometry import ray_vs_aabb, segment_sphere_hit

# 穿透等級：0=無，1=弱（手槍/衝鋒槍穿不過厚重牆），2=中（步槍），3=強（重武器）
PENETRATION_NONE = 0
PENETRATION_LIGHT = 1
PENETRATION_MEDIUM = 2
PENETRATION_HEAVY = 3


@dataclass(frozen=True, slots=True)
class Material:
    name: str
    required_pen_level: int      # 需要武器的穿透等級才能穿過
    damage_keep_mult: float      # 穿過該材質後保留的傷害比例


MATERIALS: dict[str, Material] = {
    "concrete": Material("concrete", PENETRATION_MEDIUM, 0.5),
    "wood": Material("wood", PENETRATION_LIGHT, 0.8),
    "metal": Material("metal", PENETRATION_MEDIUM, 0.6),
    "unbreakable": Material("unbreakable", PENETRATION_HEAVY + 1, 0.0),
}


@dataclass(frozen=True, slots=True)
class Wall:
    mn: Vec3
    mx: Vec3
    material: str


@dataclass(frozen=True, slots=True)
class RaycastHit:
    dist: float
    point: Vec3
    normal: Vec3
    wall: Wall


@dataclass(slots=True)
class SpikeSite:
    name: str
    center: Vec3
    radius: float = 2.0


@dataclass
class Teleporter:
    """雙向傳送門（特戰 Bind 式）：進入入口 → 瞬間移動到出口。"""
    entrance: Vec3
    exit: Vec3
    radius: float = 1.5
    cooldown: float = 3.0       # 同一玩家再次使用的冷卻
    team_restricted: int = -1   # -1 = 雙方可用, 0 = 攻方, 1 = 守方


@dataclass
class RopeZipline:
    """繩索攀爬（特戰 Split 式）：沿起點→終點方向滑行。
    玩家進入起點範圍後按 F 互動 → 沿繩索勻速移動到終點。"""
    start: Vec3                # 底部（玩家開始攀爬）
    end: Vec3                  # 頂部（玩家到達）
    speed: float = 8.0         # 攀爬速度 m/s
    radius: float = 1.2        # 觸發範圍
    bidirectional: bool = True # True = 可上可下


@dataclass
class DoorToggle:
    """可動鐵門（特戰 Ascent 式）：開/關狀態切換。
    關閉時 = 阻擋視線+移動（牆壁）；開啟時 = 可通行。
    玩家靠近門後按 F 互動 → 切換狀態。"""
    wall: Wall                 # 門的物理牆面
    toggle_pos: Vec3           # 開關互動位置
    toggle_radius: float = 2.0 # 觸發範圍
    open: bool = False         # 初始狀態：False = 關閉
    door_name: str = "door"    # 門名稱（供 UI/event 用）


@dataclass
class MapData:
    """（非 slots：需要惰性快取 _ray_hash 空間雜湊）"""
    walls: list[Wall] = field(default_factory=list)
    sites: list[SpikeSite] = field(default_factory=list)
    spawns_attackers: list[Vec3] = field(default_factory=list)
    spawns_defenders: list[Vec3] = field(default_factory=list)
    # 買槍階段活動範圍（水平 AABB：(mn, mx)）— 像《特戰英豪》：
    # 買槍期間可在出生區移動，但不可越界推進；行動期解除限制。
    buy_zone_attackers: tuple[Vec3, Vec3] | None = None
    buy_zone_defenders: tuple[Vec3, Vec3] | None = None
    bounds_min: Vec3 = field(default_factory=lambda: Vec3(-50, 0, -50))
    bounds_max: Vec3 = field(default_factory=lambda: Vec3(50, 30, 50))
    # 地圖互動機制（特戰式）
    teleporters: list[Teleporter] = field(default_factory=list)
    ropes: list[RopeZipline] = field(default_factory=list)
    doors: list[DoorToggle] = field(default_factory=list)

    def raycast(self, origin: Vec3, dir: Vec3, max_dist: float) -> RaycastHit | None:
        """最接近的牆面命中（空間雜湊 DDA，牆列表變動時自動重建）。"""
        from server.game.collision import WallSpatialHash

        h = getattr(self, "_ray_hash", None)
        if h is None or h.generation != (id(self.walls), len(self.walls)):
            h = WallSpatialHash(self.walls, cell=4.0)
            self._ray_hash = h
        hit = h.raycast(origin, dir, max_dist)
        if hit is None:
            return None
        t, normal, wall = hit
        return RaycastHit(dist=t, point=origin + dir * t, normal=normal, wall=wall)

    def los_clear(self, a: Vec3, b: Vec3) -> bool:
        """a→b 視線是否未被牆擋住（不含煙霧，煙霧由 effect 層另查）。"""
        d = b - a
        dist = d.length()
        if dist < 1e-9:
            return True
        hit = self.raycast(a, d.normalized(), dist - 0.05)
        return hit is None

    def site_named(self, name: str) -> SpikeSite | None:
        for s in self.sites:
            if s.name == name:
                return s
        return None


def default_map() -> MapData:
    """權威競技地圖 → VANTA-1（特戰英豪 Ascent 式三線雙點位）。

    幾何與驗證在 map_vanta1.py；此處僅委派，確保 UDP 伺服器、
    Workers MatchDO、測試全部使用同一張密封地圖。
    """
    from server.game.map_vanta1 import build_vanta1

    return build_vanta1()


def _legacy_default_map() -> MapData:
    """舊版 M14 地圖（保留供對照/回滾；已由 VANTA-1 取代）。

    layout（俯視，-z 攻方 / +z 守方）：

        -z = -20                    守方重生大樓（封閉，三門）
        z = +20   ┌──────────────┬───────────────┬──────────────┐
        ┌─────────┐   B 點        │   中路大樓      │   A 點        │
        │  守方    │  (-12,10)     │  (柱子隔開)     │  (12,10)     │
        │  重生大樓│   掩體        │  錯位雙門       │   掩體        │
        │  z 14~20│              │                │              │
        ├─────────┴──────────────┴───────────────┴──────────────┤
        │   B 路（半高牆+掩體）         │        A 路（半高牆+掩體）  │
        ├─────────┬──────────────┬───────────────┬──────────────┤
        │  攻方    │              │               │              │
        │  重生大樓│              │               │              │
        │  z-20~-14│              │               │              │
        └─────────┴──────────────┴───────────────┴──────────────┘

    特性（對齊《特戰英豪》戰術面）：
      * 雙方重生點封閉在建築內、三門出口 → 出生不可能直接看到敵方
      * 中路大樓 + 內柱 → 阻斷「出生→出生」中軸視線，且需繞柱推進
      * A/B 點位 + 三路推進（A 路 / 中路 / B 路），路中交錯掩體
      * 半高牆（y≤2.2）可擋視線與步槍彈，但跑跳可越視覺遮擋
    """
    m = MapData()
    t = 0.6                       # 牆厚
    hx, hz = 20.0, 20.0           # 內界半幅
    C = "concrete"
    U = "unbreakable"

    # ── 外牆（不可穿透）──────────────────────────────
    m.walls = [
        Wall(Vec3(-hx - t, 0, -hz), Vec3(-hx, 12, hz), U),
        Wall(Vec3(hx, 0, -hz), Vec3(hx + t, 12, hz), U),
        Wall(Vec3(-hx, 0, -hz - t), Vec3(hx, 12, -hz), U),
        Wall(Vec3(-hx, 0, hz), Vec3(hx, 12, hz + t), U),
    ]

    # ── 攻方重生大樓（z ∈ [-20, -14]，三門出口）────────
    m.walls += [
        Wall(Vec3(-hx, 0, -19.6), Vec3(hx, 5, -19.0), U),       # 後牆
        Wall(Vec3(-hx, 0, -14.6), Vec3(-15, 5, -14), C),        # 前牆 B 段
        Wall(Vec3(-13, 0, -14.6), Vec3(-1.8, 5, -14), C),       # 前牆 中段
        Wall(Vec3(1.8, 0, -14.6), Vec3(13, 5, -14), C),         # 前牆 A 段
        Wall(Vec3(15, 0, -14.6), Vec3(hx, 5, -14), C),          # 前牆 右段
    ]
    m.spawns_attackers = [Vec3(x, 0, -16) for x in (-14.0, -7.0, 0.0, 7.0, 14.0)]
    # 買槍區 = 重生大樓內部（行動期才解鎖全域）
    m.buy_zone_attackers = (Vec3(-hx, 0, -hz), Vec3(hx, 0, -14.0))
    m.buy_zone_defenders = (Vec3(-hx, 0, 14.0), Vec3(hx, 0, hz))

    # ── 守方重生大樓（z ∈ [14.5, 20]，三門出口）──────────
    m.walls += [
        Wall(Vec3(-hx, 0, 19.0), Vec3(hx, 5, 19.6), U),         # 後牆
        Wall(Vec3(-hx, 0, 14.5), Vec3(-15, 5, 15.1), C),        # 前牆 B 段
        Wall(Vec3(-13, 0, 14.5), Vec3(-1.8, 5, 15.1), C),       # 前牆 中段
        Wall(Vec3(1.8, 0, 14.5), Vec3(13, 5, 15.1), C),         # 前牆 A 段
        Wall(Vec3(15, 0, 14.5), Vec3(hx, 5, 15.1), C),          # 前牆 右段
    ]
    m.spawns_defenders = [Vec3(x, 0, 16) for x in (-14.0, -7.0, 0.0, 7.0, 14.0)]

    # ── 中路大樓（錯位雙門 + 內柱 → 阻斷中軸視線）────────
    m.walls += [
        Wall(Vec3(-3.5, 0, -3.6), Vec3(-1.8, 4.5, -3), C),      # -z 面 左段
        Wall(Vec3(1.8, 0, -3.6), Vec3(3.5, 4.5, -3), C),        # -z 面 右段（門 x∈[-1.8,1.8]）
        Wall(Vec3(-1.6, 0, 3), Vec3(1.6, 4.5, 3.6), C),         # +z 面（門 x<-1.6 / x>1.6）
        Wall(Vec3(-3.6, 0, -3), Vec3(-3, 4.5, 3), C),           # -x 面
        Wall(Vec3(3, 0, -3), Vec3(3.6, 4.5, 3), C),             # +x 面
        Wall(Vec3(-0.6, 0, -2.4), Vec3(0.6, 4, 2.4), C),        # 內柱（擋直線）
    ]

    # ── A 路（半高牆分段 + 2m 缺口 + 交錯掩體）────────────
    m.walls += [
        Wall(Vec3(8.5, 0, -14), Vec3(9, 2.2, -8), C),            # 路側牆 1a
        Wall(Vec3(8.5, 0, -6), Vec3(9, 2.2, 0), C),              # 路側牆 1b
        Wall(Vec3(8.5, 0, 2), Vec3(9, 2.2, 8), C),               # 路側牆 1c
        Wall(Vec3(8.5, 0, 10), Vec3(9, 2.2, 14), C),             # 路側牆 1d
        Wall(Vec3(16.5, 0, -14), Vec3(17, 2.2, -8), C),          # 路側牆 2a
        Wall(Vec3(16.5, 0, -6), Vec3(17, 2.2, 0), C),            # 路側牆 2b
        Wall(Vec3(16.5, 0, 2), Vec3(17, 2.2, 8), C),             # 路側牆 2c
        Wall(Vec3(16.5, 0, 10), Vec3(17, 2.2, 14), C),           # 路側牆 2d
        Wall(Vec3(11, 0, -8.3), Vec3(14, 2.2, -7.7), C),         # 掩體 1
        Wall(Vec3(11.5, 0, -2.3), Vec3(14.5, 2.2, -1.7), C),     # 掩體 2
        Wall(Vec3(11.5, 0, 3.7), Vec3(14, 2.2, 4.3), C),         # 掩體 3
    ]
    # ── B 路（對稱）───────────────────────────────────
    m.walls += [
        Wall(Vec3(-9, 0, -14), Vec3(-8.5, 2.2, -8), C),
        Wall(Vec3(-9, 0, -6), Vec3(-8.5, 2.2, 0), C),
        Wall(Vec3(-9, 0, 2), Vec3(-8.5, 2.2, 8), C),
        Wall(Vec3(-9, 0, 10), Vec3(-8.5, 2.2, 14), C),
        Wall(Vec3(-17, 0, -14), Vec3(-16.5, 2.2, -8), C),
        Wall(Vec3(-17, 0, -6), Vec3(-16.5, 2.2, 0), C),
        Wall(Vec3(-17, 0, 2), Vec3(-16.5, 2.2, 8), C),
        Wall(Vec3(-17, 0, 10), Vec3(-16.5, 2.2, 14), C),
        Wall(Vec3(-14, 0, -8.3), Vec3(-11, 2.2, -7.7), C),
        Wall(Vec3(-14.5, 0, -2.3), Vec3(-11.5, 2.2, -1.7), C),
        Wall(Vec3(-14, 0, 3.7), Vec3(-11.5, 2.2, 4.3), C),
    ]

    # ── Spike 點位（保持 A(12,10) / B(-12,10)）─────────
    m.sites = [SpikeSite("A", Vec3(12, 0, 10)), SpikeSite("B", Vec3(-12, 0, 10))]
    return m


class SmokeCloud:
    """M11 煙霧：球形視線阻斷器（可組合多球體模擬不規則形狀）。"""

    def __init__(self, center: Vec3, radius: float, duration: float, rng=None):
        self.center = center
        self.radius = radius
        self.time_left = duration
        self.total = duration
        self.spheres: list[tuple[Vec3, float]] = [(center, radius)]
        if rng is not None and radius >= 3.0:
            # 不規則化：向外偏移產生 4 顆子球
            import random

            for _ in range(4):
                off = Vec3(rng.uniform(-1, 1), rng.uniform(-0.3, 0.3), rng.uniform(-1, 1)).normalized()
                self.spheres.append((center + off * radius * 0.5, radius * 0.55))

    def update(self, dt: float) -> None:
        self.time_left -= dt

    @property
    def active(self) -> bool:
        return self.time_left > 0.0

    def blocks_segment(self, a: Vec3, b: Vec3) -> bool:
        for c, r in self.spheres:
            if segment_sphere_hit(a, b, c, r):
                return True
        return False
