"""
tools/maps/generator.py — 程序化地圖編輯器
==========================================
以「seed + 規則」產生競技場地圖（純程式碼編輯地圖，無 GUI）：
  * 對稱 Spike 點位（A/B）
  * 三條路線（左/中/右）的掩體牆
  * 隨機掩體（箱子）避開點位與重生點
  * 雙方重生區
輸出 server.game.mapdata.MapData 相容物件 → 可序列化、可進遊戲。

規則確保地圖「可玩」：所有牆 AABB、點位敞開、重生不卡牆、界內。
"""

from __future__ import annotations

import random

from server.core.math_core import Vec3
from server.game.mapdata import MapData, SpikeSite, Wall


def _wall_rng_walls(rng, count, x_range, z_range, y_hi, material="concrete"):
    """隨機生成掩體牆（AABB，軸向，厚 0.5）。"""
    walls = []
    for _ in range(count):
        cx = rng.uniform(*x_range)
        cz = rng.uniform(*z_range)
        w = rng.uniform(1.5, 3.5)
        d = rng.uniform(0.5, 0.8)                      # 厚度
        horizontal = rng.random() < 0.5
        if horizontal:
            walls.append(Wall(Vec3(cx - w / 2, 0, cz - d / 2), Vec3(cx + w / 2, y_hi, cz + d / 2), material))
        else:
            walls.append(Wall(Vec3(cx - d / 2, 0, cz - w / 2), Vec3(cx + d / 2, y_hi, cz + w / 2), material))
    return walls


def _far_from(points, pos, min_dist):
    for p in points:
        if pos.distance_to(p) < min_dist:
            return False
    return True


def generate_map(seed: int = 1, half: float = 20.0, y_hi: float = 3.5,
                 lane_walls: int = 6, cover_boxes: int = 8) -> MapData:
    """產生一張競技場地圖。

    layout（俯視）：
        -z (攻方重生)  ←—— 三條路線 ——→  +z (守方重生)
                          A 點 (+x)  B 點 (-x)  於 +z 側
    """
    rng = random.Random(seed)
    m = MapData()
    m.bounds_min = Vec3(-half, 0, -half)
    m.bounds_max = Vec3(half, 30, half)

    # 外牆（不可穿透）
    t = 0.6
    m.walls = [
        Wall(Vec3(-half, 0, -half - t), Vec3(half, 12, -half), "unbreakable"),
        Wall(Vec3(-half, 0, half), Vec3(half, 12, half + t), "unbreakable"),
        Wall(Vec3(-half - t, 0, -half), Vec3(-half, 12, half), "unbreakable"),
        Wall(Vec3(half, 0, -half), Vec3(half + t, 12, half), "unbreakable"),
    ]

    # 點位：A 在 (+ax, +az)、B 在 (-ax, +az)（對稱）
    ax = half * 0.45
    az = half * 0.65
    m.sites = [
        SpikeSite("A", Vec3(ax, 0, az), 2.0),
        SpikeSite("B", Vec3(-ax, 0, az), 2.0),
    ]

    # 重生區（避開點位）
    m.spawns_attackers = [Vec3(x, 0, -half + 2.0) for x in (-4.0, -2.0, 0.0, 2.0, 4.0)]
    m.spawns_defenders = [Vec3(x, 0, half - 2.0) for x in (-4.0, -2.0, 0.0, 2.0, 4.0)]
    # 買槍區：出生點周圍 6m 方形（行動期解鎖全域）
    m.buy_zone_attackers = (Vec3(-half, 0, -half), Vec3(half, 0, -half + 6.0))
    m.buy_zone_defenders = (Vec3(-half, 0, half - 6.0), Vec3(half, 0, half))
    protected = [s.center for s in m.sites] + m.spawns_attackers + m.spawns_defenders

    # 路線掩體：左/中/右三條走廊
    for lane_x in (-half * 0.55, 0.0, half * 0.55):
        for _ in range(lane_walls // 3):
            cz = rng.uniform(-half * 0.4, half * 0.4)
            w = rng.uniform(2.0, 3.0)
            wall = Wall(Vec3(lane_x - 0.25, 0, cz - w / 2), Vec3(lane_x + 0.25, y_hi, cz + w / 2), "concrete")
            if _far_from(protected, Vec3(lane_x, 0, cz), 3.0):
                m.walls.append(wall)

    # 隨機掩體箱（可穿透木箱 / 混凝土）
    for _ in range(cover_boxes):
        cx = rng.uniform(-half + 3, half - 3)
        cz = rng.uniform(-half + 3, half - 3)
        size = rng.uniform(0.8, 1.6)
        h = rng.uniform(1.0, 2.0)
        mat = rng.choice(("wood", "wood", "concrete"))
        wall = Wall(Vec3(cx - size / 2, 0, cz - size / 2), Vec3(cx + size / 2, h, cz + size / 2), mat)
        if _far_from(protected, Vec3(cx, 0, cz), 4.0):
            m.walls.append(wall)

    return m


# --------------------------------------------------------------------- #
# 驗證
# --------------------------------------------------------------------- #
def validate_map(m: MapData) -> tuple[bool, list[str]]:
    """結構驗證：界內、點位敞開、重生不卡牆、牆在界內。回傳 (通過, 問題)。"""
    issues: list[str] = []
    inside = lambda p: (m.bounds_min.x < p.x < m.bounds_max.x
                        and m.bounds_min.z < p.z < m.bounds_max.z)

    for s in m.sites:
        if not inside(s.center):
            issues.append(f"site {s.name} 超出邊界: {s.center}")

    for i, sp in enumerate(m.spawns_attackers + m.spawns_defenders):
        if not inside(sp):
            issues.append(f"spawn[{i}] 超出邊界")
        for w in m.walls:
            if _circle_hits_wall(sp, 0.5, w):
                issues.append(f"spawn[{i}] 卡進牆面 {w.material}")
                break

    for w in m.walls:
        if not (m.bounds_min.x - 1 <= w.mn.x and w.mx.x <= m.bounds_max.x + 1
                and m.bounds_min.z - 1 <= w.mn.z and w.mx.z <= m.bounds_max.z + 1):
            issues.append(f"牆超出邊界: {w.mn}..{w.mx}")

    # 點位敞開：至少 3 個方向（±x/±z）4m 內無牆
    for s in m.sites:
        open_dir = 0
        for d in (Vec3(1, 0, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1), Vec3(0, 0, -1)):
            probe = s.center + d * 4.0
            if not any(_circle_hits_wall(probe, 0.4, w) for w in m.walls):
                open_dir += 1
        if open_dir < 3:
            issues.append(f"site {s.name} 被封閉 (開放方向={open_dir}/4)")

    return len(issues) == 0, issues


def _circle_hits_wall(pos: Vec3, r: float, wall: Wall) -> bool:
    """圓 (pos, r) 與 AABB 牆是否相交（水平面）。"""
    cx = min(max(pos.x, wall.mn.x), wall.mx.x)
    cz = min(max(pos.z, wall.mn.z), wall.mx.z)
    dx, dz = pos.x - cx, pos.z - cz
    return dx * dx + dz * dz < r * r
