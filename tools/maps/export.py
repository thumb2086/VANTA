"""
tools/maps/export.py — 地圖序列化 / 載入
=======================================
MapData → JSON（可存檔/分享）→ 載入回 MapData（可直接餵給 World）。
"""

from __future__ import annotations

from server.core.math_core import Vec3
from server.game.mapdata import MapData, SpikeSite, Wall
from tools.schema import read_json, write_json


def _v(d: dict) -> Vec3:
    return Vec3(d["x"], d["y"], d["z"])


def _vec_dict(v: Vec3) -> dict:
    # 6 位小數精度 → 與 write_json 的序列化一致（round_trip 位元級相同）
    return {"x": round(v.x, 6), "y": round(v.y, 6), "z": round(v.z, 6)}


def map_to_dict(m: MapData) -> dict:
    def _zone(z):
        if z is None:
            return None
        return [_vec_dict(z[0]), _vec_dict(z[1])]

    return {
        "bounds_min": _vec_dict(m.bounds_min),
        "bounds_max": _vec_dict(m.bounds_max),
        "walls": [
            {"mn": _vec_dict(w.mn), "mx": _vec_dict(w.mx), "material": w.material}
            for w in m.walls
        ],
        "sites": [{"name": s.name, "center": _vec_dict(s.center), "radius": s.radius} for s in m.sites],
        "spawns_attackers": [_vec_dict(p) for p in m.spawns_attackers],
        "spawns_defenders": [_vec_dict(p) for p in m.spawns_defenders],
        "buy_zone_attackers": _zone(m.buy_zone_attackers),
        "buy_zone_defenders": _zone(m.buy_zone_defenders),
    }


def dict_to_map(d: dict) -> MapData:
    m = MapData()
    m.bounds_min = _v(d["bounds_min"])
    m.bounds_max = _v(d["bounds_max"])
    m.walls = [
        Wall(_v(w["mn"]), _v(w["mx"]), w["material"])
        for w in d["walls"]
    ]
    m.sites = [SpikeSite(s["name"], _v(s["center"]), s.get("radius", 2.0)) for s in d["sites"]]
    m.spawns_attackers = [_v(p) for p in d["spawns_attackers"]]
    m.spawns_defenders = [_v(p) for p in d["spawns_defenders"]]
    m.buy_zone_attackers = tuple(_v(c) for c in d["buy_zone_attackers"]) if d.get("buy_zone_attackers") else None
    m.buy_zone_defenders = tuple(_v(c) for c in d["buy_zone_defenders"]) if d.get("buy_zone_defenders") else None
    return m


def save_map(path: str, m: MapData) -> None:
    write_json(path, map_to_dict(m))


def load_map(path: str) -> MapData:
    return dict_to_map(read_json(path))
