"""
server/game/collision.py — 移動碰撞（M14 強化）
================================================
將「角色移動」與「地圖牆面（AABB）」整合：
  * 玩家以圓柱近似（半徑 0.35m、高 1.8m）
  * 牆面碰撞：水平推離（最近點法）+ 消除朝牆速度分量 → 可沿牆滑移
  * 天花板：跳躍頂到低矮遮蔽時壓回並歸零上速度
  * 玩家間碰撞：5v5 之間不可重疊（圓形推離）

此處只處理「位置修正」；移動邏輯仍由 MovementController 權威決定。
確定性：固定牆面順序 + 固定玩家配對順序 + 固定迭代次數。
"""

from __future__ import annotations

import math

from server.core.math_core import Vec3
from server.game.mapdata import Wall

PLAYER_RADIUS = 0.35
PLAYER_HEIGHT = 1.8
COLLISION_PASSES = 3


def _push_out(
    x: float, z: float, r: float, wall: Wall
) -> tuple[float, float, float] | None:
    """計算圓心 (x,z) 半徑 r 相對 AABB 牆的推離 (nx, nz, push)。無碰撞回 None。"""
    mnx, mxx = wall.mn.x, wall.mx.x
    mnz, mxz = wall.mn.z, wall.mx.z

    # 圓心在 AABB 外 → 最近點法
    cx = min(max(x, mnx), mxx)
    cz = min(max(z, mnz), mxz)
    dx, dz = x - cx, z - cz
    d2 = dx * dx + dz * dz
    if d2 >= r * r - 1e-12:
        return None
    if d2 > 1e-12:
        d = math.sqrt(d2)
        push = r - d
        return (dx / d, dz / d, push)
    # 圓心在 AABB 內（罕見）→ 四個面向外推，取最小位移
    cands = [
        ((mnx - r) - x, -1.0, 0.0),
        ((mxx + r) - x, 1.0, 0.0),
        ((mnz - r) - z, 0.0, -1.0),
        ((mxz + r) - z, 0.0, 1.0),
    ]
    best = min(cands, key=lambda c: abs(c[0]))
    return (best[1], best[2], abs(best[0]))


def resolve_player_wall(p, wall: Wall) -> bool:
    """單一玩家 vs 單一牆。回傳是否發生推離。"""
    y = p.pos.y
    # 垂直區間重疊檢查（玩家 [y, y+height] vs 牆 [mn.y, mx.y]）
    if y + PLAYER_HEIGHT <= wall.mn.y or y >= wall.mx.y:
        return False
    r = _push_out(p.pos.x, p.pos.z, PLAYER_RADIUS, wall)
    if r is None:
        return False
    nx, nz, push = r
    p.pos = Vec3(p.pos.x + nx * push, p.pos.y, p.pos.z + nz * push)
    # 消除朝牆的速度分量（保留切線 → 沿牆滑移）
    vn = p.vel.x * nx + p.vel.z * nz
    if vn < 0.0:
        p.vel = Vec3(p.vel.x - vn * nx, p.vel.y, p.vel.z - vn * nz)
    return True


def resolve_ceiling(p, wall: Wall) -> bool:
    """跳躍頂到天花板 → 壓回並歸零上速度。"""
    head = p.pos.y + PLAYER_HEIGHT
    if head <= wall.mx.y or p.pos.y >= wall.mx.y:
        return False
    # 水平重疊
    if (p.pos.x + PLAYER_RADIUS <= wall.mn.x or p.pos.x - PLAYER_RADIUS >= wall.mx.x
            or p.pos.z + PLAYER_RADIUS <= wall.mn.z or p.pos.z - PLAYER_RADIUS >= wall.mx.z):
        return False
    p.pos = Vec3(p.pos.x, wall.mx.y - PLAYER_HEIGHT, p.pos.z)
    if p.vel.y > 0.0:
        p.vel = Vec3(p.vel.x, 0.0, p.vel.z)
    return True


def resolve_player_player(a, b) -> bool:
    """兩個玩家圓形推離（各推一半）。回傳是否發生推離。"""
    dx = b.pos.x - a.pos.x
    dz = b.pos.z - a.pos.z
    d2 = dx * dx + dz * dz
    min_d = 2.0 * PLAYER_RADIUS
    if d2 >= min_d * min_d:
        return False
    if d2 < 1e-12:
        dx, dz, d = 1.0, 0.0, 0.0          # 完全重合：朝固定方向各推半徑
    else:
        d = math.sqrt(d2)
        dx, dz = dx / d, dz / d
    half = (min_d - d) * 0.5
    a.pos = Vec3(a.pos.x - dx * half, a.pos.y, a.pos.z - dz * half)
    b.pos = Vec3(b.pos.x + dx * half, b.pos.y, b.pos.z + dz * half)
    # 消除「接近方向」的相對速度（防止穿人/黏人）
    vrel = (a.vel.x - b.vel.x) * dx + (a.vel.z - b.vel.z) * dz
    if vrel > 0.0:
        a.vel = Vec3(a.vel.x - vrel * dx, a.vel.y, a.vel.z - vrel * dz)
        b.vel = Vec3(b.vel.x + vrel * dx, b.vel.y, b.vel.z + vrel * dz)
    return True


def resolve_world(world) -> None:
    """世界級碰撞解析：牆面 × 多次迭代 → 玩家間。

    效能優化（行為不變）：
      1. 牆面用空間雜湊寬相位（WallSpatialHash）→ 每玩家只測附近牆，
         遠牆 _push_out 必回 None，故結果與全測一致（位元級相同）。
      2. 玩家配對用 AABB 早退（|dx|>2r 或 |dz|>2r 直接跳過）。
    """
    walls = getattr(world, "_wall_hash", None)
    if walls is None or walls.generation != (id(world.map_data.walls), len(world.map_data.walls)):
        walls = WallSpatialHash(world.map_data.walls, cell=4.0)
        world._wall_hash = walls

    for _ in range(COLLISION_PASSES):
        moved = False
        for p in world.players:
            if not p.alive:
                continue
            for wall in walls.query(p.pos.x, p.pos.z, PLAYER_RADIUS):
                moved |= resolve_player_wall(p, wall)
            for wall in walls.query(p.pos.x, p.pos.z, PLAYER_RADIUS):
                moved |= resolve_ceiling(p, wall)
        for i in range(len(world.players)):
            a = world.players[i]
            if not a.alive:
                continue
            for j in range(i + 1, len(world.players)):
                b = world.players[j]
                if not b.alive:
                    continue
                # AABB 早退：水平距離大於兩半徑和 → 不可能碰撞
                dx = b.pos.x - a.pos.x
                if dx > 2 * PLAYER_RADIUS or dx < -2 * PLAYER_RADIUS:
                    continue
                dz = b.pos.z - a.pos.z
                if dz > 2 * PLAYER_RADIUS or dz < -2 * PLAYER_RADIUS:
                    continue
                moved |= resolve_player_player(a, b)
        if not moved:
            break


class WallSpatialHash:
    """牆面空間雜湊（寬相位）。行為不變：只回傳「可能重疊」的牆。

    確定性：每個格子內的牆依「原列表索引」排序；查詢依固定格子順序回傳。
    """

    def __init__(self, walls, cell: float = 4.0):
        self.cell = cell
        # 快取指紋：append（len 變）與整列替換（id 變）都會觸發重建
        self.generation = (id(walls), len(walls))
        self._walls = list(walls)
        self._grid: dict[tuple[int, int], list[int]] = {}
        for idx, w in enumerate(self._walls):
            # 牆的 AABB 擴展玩家半徑（含圓柱外推）
            mnx = int(math.floor((w.mn.x - PLAYER_RADIUS) / cell))
            mxx = int(math.floor((w.mx.x + PLAYER_RADIUS) / cell))
            mnz = int(math.floor((w.mn.z - PLAYER_RADIUS) / cell))
            mxz = int(math.floor((w.mx.z + PLAYER_RADIUS) / cell))
            for cx in range(mnx, mxx + 1):
                for cz in range(mnz, mxz + 1):
                    self._grid.setdefault((cx, cz), []).append(idx)
        # 每格依原索引排序 → 確定性
        for key in self._grid:
            self._grid[key].sort()

    def query(self, x: float, z: float, radius: float) -> list:
        """回傳可能與圓 (x,z,r) 重疊的牆（依格子順序 + 原索引）。"""
        walls = self._walls
        out = []
        cx0 = int(math.floor((x - radius) / self.cell))
        cx1 = int(math.floor((x + radius) / self.cell))
        cz0 = int(math.floor((z - radius) / self.cell))
        cz1 = int(math.floor((z + radius) / self.cell))
        for cx in range(cx0, cx1 + 1):
            for cz in range(cz0, cz1 + 1):
                for idx in self._grid.get((cx, cz), ()):
                    out.append(walls[idx])
        return out

    def raycast(self, origin: Vec3, dir: Vec3,
                max_dist: float) -> tuple[float, Vec3, Wall] | None:
        """DDA 網格步進射線：只測試射線穿過的格子內的牆（比全量快 ~10x）。

        回傳 (dist, normal, wall)；無命中回 None。確定性：格子順序固定。
        """
        from server.game.geometry import ray_vs_aabb

        ox, oz = origin.x, origin.z
        dx, dz = dir.x, dir.z
        cx = int(math.floor(ox / self.cell))
        cz = int(math.floor(oz / self.cell))
        step_x = 1 if dx >= 0 else -1
        step_z = 1 if dz >= 0 else -1
        t_max_x = ((cx + (1 if dx >= 0 else 0)) * self.cell - ox) / dx if dx != 0.0 else float("inf")
        t_max_z = ((cz + (1 if dz >= 0 else 0)) * self.cell - oz) / dz if dz != 0.0 else float("inf")
        t_delta_x = abs(self.cell / dx) if dx != 0.0 else float("inf")
        t_delta_z = abs(self.cell / dz) if dz != 0.0 else float("inf")
        seen: set[int] = set()
        best: tuple[float, Vec3, Wall] | None = None
        for _ in range(64):
            for idx in self._grid.get((cx, cz), ()):
                if idx in seen:
                    continue
                seen.add(idx)
                w = self._walls[idx]
                hit = ray_vs_aabb(origin, dir, w.mn, w.mx, max_dist)
                if hit is not None and (best is None or hit[0] < best[0]):
                    best = (hit[0], hit[1], w)
            if t_max_x < t_max_z:
                if t_max_x > max_dist:
                    break
                cx += step_x
                t_max_x += t_delta_x
            else:
                if t_max_z > max_dist:
                    break
                cz += step_z
                t_max_z += t_delta_z
        return best
