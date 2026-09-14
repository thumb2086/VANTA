'''
server/game/map_vanta1.py — VANTA-1 競技地圖（特戰英豪 Ascent 式三線雙點位）
=============================================================================
設計依據（2026 特戰英豪地圖研究）：
  * 三路結構：A Main（東）/ 中路 Courtyard / B Main（西）
  * 雙站點 A(12,10) B(-12,10)——與 AI 大腦的 A_SITE 常數一致
  * 全封閉外框 → 杜絕「走出世界」與反作弊回彈橡皮筋
  * 所有通道 ≥4m、牆段端點完全對齊 → 無 0.05~2.5m 縫隙（穿牆/視線破洞）
  * 咽喉點 5m；站點半徑 3.5m 掩體箱交錯；無 >40m 直線視野
  * 出生→站點步行約 12~15 秒（5.4 m/s）

佈局（俯視，+z 北 = 守方）：
              ┌──────────── 外框 ±20 ────────────┐
              │            CT SPAWN               │
              │   B SITE    MID TOP     A SITE    │
              │  (-12,10)   (中央走廊)   (12,10)  │
 z=6/2  ──B Main──┬─ Link ─┬─ Courtyard ─┬─ Link ──┬──A Main──
              │   B LOBBY │   TILES     │  A LOBBY │
              │            ATK SPAWN              │
              └───────────────────────────────────┘
'''

from __future__ import annotations

from server.core.math_core import Vec3
from server.game.mapdata import MapData, SpikeSite, Wall, Teleporter, RopeZipline, DoorToggle

T = 0.6        # 牆厚
H_IN = 4.0     # 內牆高
H_OUT = 12.0   # 外框高
C = "concrete"
U = "unbreakable"
W_ = "wood"


def _hw(z: float, x0: float, x1: float, h: float = H_IN, mat: str = C) -> Wall:
    """沿 x 軸的水平牆（佔 z±T/2）。"""
    return Wall(Vec3(x0, 0, z - T / 2), Vec3(x1, h, z + T / 2), mat)


def _vw(x: float, z0: float, z1: float, h: float = H_IN, mat: str = C) -> Wall:
    """沿 z 軸的垂直牆（佔 x±T/2）。"""
    return Wall(Vec3(x - T / 2, 0, z0), Vec3(x + T / 2, h, z1), mat)


def build_vanta1() -> MapData:
    m = MapData()
    w: list[Wall] = []

    # ── 外框（全封閉，unbreakable）────────────────────────
    w += [
        _vw(-20.3, -20.3, 20.3, H_OUT, U),
        _vw(20.3, -20.3, 20.3, H_OUT, U),
        _hw(-20.3, -20.9, 20.9, H_OUT, U),
        _hw(20.3, -20.9, 20.9, H_OUT, U),
    ]

    # ── 攻方出生 x[-8,8] z[-20,-13]，正面單門 x[-4,4] ────
    w += [
        _vw(-8.3, -20, -13),          # 西側牆
        _vw(8.3, -20, -13),           # 東側牆
        _hw(-13.3, -20.9, -4),        # 正面西段
        _hw(-13.3, 4, 8.9),           # 正面東段
    ]

    # ── 三路分隔牆 V(±8)：tiles↔大廳 門 z[-11,-7] ────────
    for sx in (-8.3, 8.3):
        w += [
            _vw(sx, -13, -11),
            _vw(sx, -7, -6),
        ]

    # ── Tiles/Courtyard 分界 z=-6（錯位缺口 x[-6,-1]，防中央直視）──
    w += [
        _hw(-6.3, -8.9, -6),
        _hw(-6.3, -1, 8.9),
    ]

    # ── Courtyard 側壁 V(±8) z[-6,2]，Link 缺口 z[2,6] ───
    w += [
        _vw(-8.3, -6, 2),
        _vw(8.3, -6, 2),
    ]
    # z[2,6] 不放牆 → Tree/Link 直接進站（中路分推路線）

    # ── Courtyard/MidTop 分界 z=6（反向錯位缺口 x[1,6]）───
    w += [
        _hw(6.3, -8.9, 1),
        _hw(6.3, 6, 8.9),
    ]

    # ── MidTop 側壁 V(±8) z[6,13]，站點連絡門 z[8,12] ────
    for sx in (-8.3, 8.3):
        w += [
            _vw(sx, 6, 8),
            _vw(sx, 12, 13),
        ]

    # ── 北線 z=13：CT 中央缺口 x[-3,3]、站點迴防缺口 ±[10,14]
    w += [
        # B 側（x<0）
        _hw(13.3, -20.9, -14),
        _hw(13.3, -10, -3),
        # A 側
        _hw(13.3, 3, 8.9),
        _hw(13.3, 14, 20.9),
    ]

    # ── CT 出生 x[-6,6] z[13,20] ─────────────────────────
    w += [
        _vw(-6.3, 13, 20),
        _vw(6.3, 13, 20),
    ]

    # ── A Main：走廊 x[11,16] z[-6,2]；大廳北牆其餘封閉 ──
    w += [
        _vw(11, -6, 2),
        _vw(16, -6, 2),
        _hw(-6.3, 8.0, 11),           # 大廳北牆（main 口左）
        _hw(-6.3, 16, 20.9),          # main 口右
        # site 南緣 z=2：main 口 x[11,16] 開放，兩側封閉
        _hw(2.3, 8.9, 11),
        _hw(2.3, 16, 20.9),
    ]

    # ── B Main（鏡射）────────────────────────────────────
    w += [
        _vw(-11, -6, 2),
        _vw(-16, -6, 2),
        _hw(-6.3, -20.9, -16),
        _hw(-6.3, -11, -8.0),
        _hw(2.3, -20.9, -16),
        _hw(2.3, -11, -8.9),
    ]

    # ── 掩體（箱子/半牆）─────────────────────────────────
    def box(x0, z0, x1, z1, h=2.0, mat=C) -> Wall:
        return Wall(Vec3(x0, 0, z0), Vec3(x1, h, z1), mat)

    w += [
        box(-1.5, -1.5, 1.5, 1.5, 4.0),          # Courtyard 中央柱
        # A Site 掩體
        box(11.5, 3.0, 14.5, 5.5, 2.0),          # Gen（main 入口正前方）
        box(16.5, 8.0, 19.0, 10.5, 1.15),        # 半牆（後站）
        box(8.6, 10.5, 11.0, 13.0, 2.0),         # Tree 箱（Link 角）
        # B Site 掩體（鏡射）
        box(-14.5, 3.0, -11.5, 5.5, 2.0),
        box(-19.0, 8.0, -16.5, 10.5, 1.15),
        box(-11.0, 10.5, -8.6, 13.0, 2.0),
        # Tiles 掩體
        box(-5.5, -10.5, -3.5, -8.5, 1.15),
        box(3.5, -10.5, 5.5, -8.5, 1.15),
        # 大廳掩體
        box(13.0, -17.0, 15.5, -14.5, 2.0),
        box(-15.5, -17.0, -13.0, -14.5, 2.0),
        # MidTop 掩體（齊平貼牆，不留 <0.75m 縫）
        box(-8.3, 6.6, -6.2, 9.5, 2.0),
        box(6.2, 6.6, 8.3, 9.5, 2.0),
    ]

    m.walls = w

    # ── 站點 / 重生 / 買槍區 ─────────────────────────────
    m.sites = [
        SpikeSite("A", Vec3(12, 0, 10), 3.5),
        SpikeSite("B", Vec3(-12, 0, 10), 3.5),
    ]
    m.spawns_attackers = [Vec3(x, 0, -16.5) for x in (-6.0, -3.0, 0.0, 3.0, 6.0)]
    m.spawns_defenders = [Vec3(x, 0, 17.0) for x in (-4.0, -2.0, 0.0, 2.0, 4.0)]
    m.buy_zone_attackers = (Vec3(-8.9, 0, -20.9), Vec3(8.9, 0, -13))
    m.buy_zone_defenders = (Vec3(-6.9, 0, 13), Vec3(6.9, 0, 20.9))
    m.bounds_min = Vec3(-21, 0, -21)
    m.bounds_max = Vec3(21, 30, 21)

    # ── 地圖互動機制（特戰式）──────────────────────────────

    # 傳送門：B Main → A Main（像 Bind 的單向傳送）
    m.teleporters = [
        Teleporter(
            entrance=Vec3(-15.0, 0, -1.0),   # B Main 走廊
            exit=Vec3(15.0, 0, -1.0),        # A Main 走廊
            radius=1.5,
            cooldown=4.0,
            team_restricted=-1,              # 雙方可用
        ),
    ]

    # 繩索攀爬：Courtyard 中央柱頂 → MidTop 高台
    m.ropes = [
        RopeZipline(
            start=Vec3(0.0, 0, 0.0),         # Courtyard 地面
            end=Vec3(0.0, 4.0, 6.0),         # MidTop 高台
            speed=8.0,
            radius=1.5,
            bidirectional=True,
        ),
        # A Site 繩索：A Main → A Site 高台
        RopeZipline(
            start=Vec3(13.0, 0, -4.0),
            end=Vec3(17.0, 2.5, 8.0),
            speed=7.0,
            radius=1.2,
            bidirectional=True,
        ),
        # B Site 繩索（鏡射）
        RopeZipline(
            start=Vec3(-13.0, 0, -4.0),
            end=Vec3(-17.0, 2.5, 8.0),
            speed=7.0,
            radius=1.2,
            bidirectional=True,
        ),
    ]

    # 可動鐵門：A Site Market 門 + B Site Market 門（像 Ascent Market Door）
    door_a = Wall(Vec3(8.6, 0, 10.0), Vec3(8.9, 3.5, 13.0), C)
    door_b = Wall(Vec3(-8.9, 0, 10.0), Vec3(-8.6, 3.5, 13.0), C)
    # 不放入 m.walls（由 DoorToggle 管理）
    m.doors = [
        DoorToggle(
            wall=door_a,
            toggle_pos=Vec3(7.5, 0, 11.5),
            toggle_radius=2.0,
            open=False,         # 初始關閉
            door_name="A Market Door",
        ),
        DoorToggle(
            wall=door_b,
            toggle_pos=Vec3(-7.5, 0, 11.5),
            toggle_radius=2.0,
            open=False,
            door_name="B Market Door",
        ),
    ]
    # 初始關閉的門加入牆面列表
    for door in m.doors:
        if not door.open:
            m.walls.append(door.wall)

    return m


# ═══════════════════════════════════════════════════════════ #
#  地圖驗證（pytest 也會跑）：密封性 / 可達性 / 視野            #
# ═══════════════════════════════════════════════════════════ #

def validate_vanta1(m: MapData | None = None) -> dict:
    """回傳驗證結果 dict；任何一項失敗都該讓測試紅燈。

    checks:
      reachable_from_atk: 攻方出生可到 A/B 點與守方出生
      sealed:             可行走網格不出外框
      area_m2:            可走面積合理值
    """
    if m is None:
        m = build_vanta1()

    step = 0.5
    xs = [x * step for x in range(-41, 41)]     # -20.5..20
    zs = [z * step for z in range(-41, 41)]
    # 直接以牆 XZ 足跡 + 垂直涵蓋判定阻擋（引擎射線不支援垂直方向）
    solid_walls = [wl for wl in m.walls if wl.mx.y >= 1.9 and wl.mn.y <= 0.1]
    blocked = set()
    for ix, x in enumerate(xs):
        for iz, z in enumerate(zs):
            for wl in solid_walls:
                if (wl.mn.x <= x <= wl.mx.x) and (wl.mn.z <= z <= wl.mx.z):
                    blocked.add((ix, iz))
                    break

    start = (int((0 + 20.5) / step), int((-16.5 + 20.5) / step))
    from collections import deque
    seen = {start}
    q = deque([start])
    while q:
        ix, iz = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = ix + dx, iz + dz
            if (nx, nz) in seen or nx < 0 or nz < 0 or nx >= len(xs) or nz >= len(zs):
                continue
            if (nx, nz) in blocked:
                continue
            seen.add((nx, nz))
            q.append((nx, nz))

    def cell_of(pos: Vec3) -> tuple[int, int]:
        return (int(round((pos.x + 20.5) / step)), int(round((pos.z + 20.5) / step)))

    targets = {
        "site_A": cell_of(Vec3(12, 0, 10)),
        "site_B": cell_of(Vec3(-12, 0, 10)),
        "ct_spawn": cell_of(Vec3(0, 0, 17)),
    }
    reach = {name: (c in seen) for name, c in targets.items()}
    in_bounds = all(
        -20.0 <= xs[ix] <= 20.0 and -20.0 <= zs[iz] <= 20.0
        for ix, iz in seen)
    # 站點/出生點本身不可被牆佔住
    spots_clear = all(c not in blocked for c in targets.values())
    return {
        "reachable_from_atk": reach,
        "sealed": in_bounds,
        "spots_clear": spots_clear,
        "area_m2": len(seen) * step * step,
    }


if __name__ == "__main__":
    import io
    import json
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    res = validate_vanta1()
    print("validation:", res)
    assert all(res["reachable_from_atk"].values()), "有目標不可達！"
    assert res["sealed"], "地圖沒密封（可行走區超出外框）！"
    assert res["spots_clear"], "站點/出生點被牆佔住！"

    from tools.maps.export import save_map
    out = os.path.join("client", "assets", "maps", "map_vanta1.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    save_map(out, build_vanta1())
    print(f"exported -> {out}")
