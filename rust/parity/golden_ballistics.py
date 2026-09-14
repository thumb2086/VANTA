"""
rust/parity/golden_ballistics.py — 彈道/Hitbox/穿透 黃金資料
============================================================
固定場景（玩家位置/生死/血量 + 牆面材質）+ 固定射擊清單 →
輸出 scene.bin（場景）＋ expected_ballistics.bin（Python 模擬結果）。
Rust 端讀場景重跑，必須位元組級一致（含跨發狀態：傷害累積/死亡跳過/溢傷）。

武器：0=vandal(40,pen2) 1=classic(26,pen0) 2=operator(150,pen2)
區域：0=頭(4x) 1=身(1x) 2=腿(0.85x)
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server.core.math_core import Vec3
from server.game.ballistics import resolve_hitscan
from server.game.entities import World
from server.game.mapdata import MapData, Wall
from server.game.weapons import weapon

OUT = os.path.dirname(os.path.abspath(__file__))

WALLS = [
    # (mn, mx, material)  — 薄木牆
    (Vec3(0, 0, 4), Vec3(0.2, 4, 4.2), "wood"),
    # 混凝土箱（x=10 射線不會碰到）
    (Vec3(-2, 0, 5), Vec3(2, 4, 7), "concrete"),
    # 不可穿透後牆
    (Vec3(-25, 0, 19), Vec3(25, 12, 20), "unbreakable"),
]

# (slot, feet, alive, health)
PLAYERS = [
    (0, Vec3(10, 0, 0), True, 100.0),    # 射手
    (1, Vec3(10, 0, 8), True, 100.0),    # 木牆後
    (2, Vec3(10, 0, 6), True, 100.0),
    (3, Vec3(10, 0, 21), True, 100.0),   # 不可穿透牆後
] + [(i, Vec3(50, 0, 50), False, 0.0) for i in range(4, 10)]   # 死亡，略過

# (weapon_id, origin, dir) — 依序執行（狀態跨發保留）
SHOTS = [
    (0, Vec3(10, 1.6, 0), (Vec3(10, 1.0, 8) - Vec3(10, 1.6, 0)).normalized()),   # 1: vandal 穿木牆打身
    (0, Vec3(10, 1.6, 0), (Vec3(10, 1.0, 6) - Vec3(10, 1.6, 0)).normalized()),   # 2: vandal 穿木牆打 p2 身
    (1, Vec3(10, 1.6, 0), (Vec3(10, 1.0, 8) - Vec3(10, 1.6, 0)).normalized()),   # 3: classic 穿不過 → 無命中
    (2, Vec3(10, 1.6, 0), (Vec3(10, 1.0, 21) - Vec3(10, 1.6, 0)).normalized()),  # 4: operator 穿不過 unbreakable
    (0, Vec3(10, 1.6, 0), (Vec3(10, 0.5, 8) - Vec3(10, 1.6, 0)).normalized()),   # 5: vandal 打 p1 腿（穿牆 0.8×0.85）
    (0, Vec3(10, 1.6, 0), (Vec3(10, 1.8, 8) - Vec3(10, 1.6, 0)).normalized()),   # 6: vandal 爆頭（溢傷擊殺）
]


def build_world() -> World:
    world = World()
    world.map_data = MapData()
    for mn, mx, mat in WALLS:
        world.map_data.walls.append(Wall(mn, mx, mat))
    world.map_data.bounds_min = Vec3(-50, 0, -50)
    world.map_data.bounds_max = Vec3(50, 30, 50)
    for slot, feet, alive, hp in PLAYERS:
        p = world.players[slot]
        p.pos = feet
        p.alive = alive
        p.health = hp
    return world


def main() -> None:
    # 場景
    with open(os.path.join(OUT, "scene_ballistics.bin"), "wb") as f:
        f.write(struct.pack("<I", len(WALLS)))
        for mn, mx, mat in WALLS:
            for v in (mn, mx):
                f.write(struct.pack("<ddd", v.x, v.y, v.z))
            f.write(bytes([{"wood": 1, "concrete": 0, "metal": 2, "unbreakable": 3}[mat]]))
        f.write(struct.pack("<I", len(PLAYERS)))
        for slot, feet, alive, hp in PLAYERS:
            f.write(struct.pack("<ddd", feet.x, feet.y, feet.z))
            f.write(bytes([1 if alive else 0]))
            f.write(struct.pack("<d", hp))
        f.write(struct.pack("<I", len(SHOTS)))
        for wid, origin, d in SHOTS:
            f.write(bytes([wid]))
            f.write(struct.pack("<ddd", origin.x, origin.y, origin.z))
            f.write(struct.pack("<ddd", d.x, d.y, d.z))

    # 模擬（跨發狀態保留）
    world = build_world()
    targets = {i: world.players[i].pos for i in range(10)}
    results = []
    for wid, origin, d in SHOTS:
        stats = (weapon("vandal"), weapon("classic"), weapon("operator"))[wid]
        res = resolve_hitscan(world, world.map_data, 0, origin, d, stats, targets)
        hits = []
        for h in res.hits:
            region = {"head": 0, "body": 1, "legs": 2}[h.region]
            hits.append((h.target_slot, region, h.base_damage, h.final_damage, h.penetrated_walls))
        results.append(hits)

    with open(os.path.join(OUT, "expected_ballistics.bin"), "wb") as f:
        for hits in results:
            f.write(struct.pack("<I", len(hits)))
            for slot, region, base, dealt, wh in hits:
                f.write(struct.pack("<i", slot))
                f.write(bytes([region]))
                f.write(struct.pack("<ddi", base, dealt, wh))
    print(f"彈道黃金資料完成: {len(SHOTS)} 發（場景含木牆/混凝土/不可穿透牆）")


if __name__ == "__main__":
    main()
