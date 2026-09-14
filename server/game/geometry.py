"""
server/game/geometry.py — 幾何檢測（確定性，純函式）
====================================================
射線 vs 球體 / 膠囊 / AABB，以及視線判定。全部以 float64 運算，
無平台相依函式，供彈道、穿透、視線遮蔽、Rollback 命中共用。
"""

from __future__ import annotations

import math

from server.core.math_core import EPSILON, Vec3


def ray_vs_sphere(
    origin: Vec3, dir: Vec3, center: Vec3, radius: float, max_dist: float
) -> float | None:
    """回傳命中距離 t ∈ [0, max_dist]，無命中回 None。"""
    oc = origin - center
    a = dir.dot(dir)
    b = 2.0 * oc.dot(dir)
    c = oc.dot(oc) - radius * radius
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None
    sq = math.sqrt(disc)
    t1 = (-b - sq) / (2.0 * a)
    t2 = (-b + sq) / (2.0 * a)
    t = t1 if t1 >= 0.0 else t2
    if 0.0 <= t <= max_dist:
        return t
    return None


def ray_vs_capsule(
    origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, radius: float, max_dist: float
) -> float | None:
    """膠囊 = 軸 a→b 的掃掠球體。回傳最近命中距離，無命中回 None。"""
    axis = b - a
    length = axis.length()
    if length < EPSILON:
        return ray_vs_sphere(origin, dir, a, radius, max_dist)
    u = axis * (1.0 / length)

    # 1) 無限圓柱（正確的射線-軸最近推導：W = origin - a）
    d = dir.normalized()
    W = origin - a
    c = d.dot(u)                      # d·u
    denom = 1.0 - c * c
    t0: float | None = None
    if denom > 1e-9:
        # t_c = [(W·u)(d·u) - W·d] / (1-(d·u)^2)
        t_c = ((W.dot(u)) * c - W.dot(d)) / denom
        closest = origin + d * t_c
        proj = closest.dot(u) - a.dot(u)
        if 0.0 <= proj <= length:
            perp = closest - (a + u * proj)
            d2 = perp.length_sq()
            if d2 <= radius * radius:
                entry = t_c - math.sqrt(max(0.0, radius * radius - d2))
                if entry >= 0.0:
                    t0 = entry
    # 2) 兩端球帽
    t1 = ray_vs_sphere(origin, dir, a, radius, max_dist)
    t2 = ray_vs_sphere(origin, dir, b, radius, max_dist)
    cands = [t for t in (t0, t1, t2) if t is not None]
    if not cands:
        return None
    t = min(cands)
    return t if t <= max_dist else None


def ray_vs_aabb(
    origin: Vec3, dir: Vec3, mn: Vec3, mx: Vec3, max_dist: float
) -> tuple[float, Vec3] | None:
    """AABB 射線檢測（slab 法）。回傳 (t, 法線)。"""
    tmin, tmax = 0.0, max_dist
    hit_axis = -1
    for i in range(3):
        o = [origin.x, origin.y, origin.z][i]
        d = [dir.x, dir.y, dir.z][i]
        mn_i = [mn.x, mn.y, mn.z][i]
        mx_i = [mx.x, mx.y, mx.z][i]
        if abs(d) < 1e-12:
            if o < mn_i or o > mx_i:
                return None
            continue
        inv = 1.0 / d
        t1 = (mn_i - o) * inv
        t2 = (mx_i - o) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tmin:
            tmin, hit_axis = t1, i
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    if tmin < 0.0 or tmin > max_dist or hit_axis < 0:
        return None
    normal = Vec3()
    if hit_axis == 0:
        normal = Vec3(-1.0, 0.0, 0.0) if origin.x < (mn.x + mx.x) * 0.5 else Vec3(1.0, 0.0, 0.0)
    elif hit_axis == 1:
        normal = Vec3(0.0, -1.0, 0.0) if origin.y < (mn.y + mx.y) * 0.5 else Vec3(0.0, 1.0, 0.0)
    else:
        normal = Vec3(0.0, 0.0, -1.0) if origin.z < (mn.z + mx.z) * 0.5 else Vec3(0.0, 0.0, 1.0)
    return tmin, normal


def segment_sphere_hit(a: Vec3, b: Vec3, center: Vec3, radius: float) -> bool:
    """線段 a-b 與球體是否相交（視線遮蔽用）。"""
    ab = b - a
    t = max(0.0, min(1.0, (center - a).dot(ab) / ab.length_sq()))
    return (a + ab * t).distance_to(center) <= radius


def segment_capsule_hit(a: Vec3, b: Vec3, c0: Vec3, c1: Vec3, radius: float) -> bool:
    """線段 a-b 與膠囊是否相交。"""
    return ray_vs_capsule(a, (b - a).normalized(), c0, c1, radius, (b - a).length()) is not None
