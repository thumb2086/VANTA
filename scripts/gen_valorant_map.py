#!/usr/bin/env python3
"""
產生 Valorant 風格地圖（含高低差/掩體/通道/3 站點）
用法：python gen_valorant_map.py > client/assets/maps/valorant_map.json
"""
import json
import math

def make_wall(mn, mx, material="concrete"):
    return {"mn": {"x": mn[0], "y": mn[1], "z": mn[2]},
            "mx": {"x": mx[0], "y": mx[1], "z": mx[2]},
            "material": material}

def make_site(name, center, radius=3.0):
    return {"name": name, "center": {"x": center[0], "y": 0, "z": center[2]}, "radius": radius}

def make_spawn(x, z):
    return {"x": x, "y": 0, "z": z}

# ============================================================
# 地圖配置：三路設計 + 高低差 + 3 站點
# ============================================================
# 地圖大小：60x60 單位
# 中央高台：y=3（二樓）
# 地面：y=0（一樓）
# 坡道連接高低差

walls = []
sites = []
spawns_a = []
spawns_d = []

# === 外牆 ===
walls.append(make_wall([-30, 0, -30], [-29.4, 8, 30]))   # 左牆
walls.append(make_wall([29.4, 0, -30], [30, 8, 30]))     # 右牆
walls.append(make_wall([-30, 0, -30], [30, 8, -29.4]))   # 前牆
walls.append(make_wall([-30, 0, 29.4], [30, 8, 30]))     # 後牆

# === 中央高台（二樓平台）===
# 主平台
walls.append(make_wall([-8, 3, -8], [8, 3.4, 8]))        # 高台地面
walls.append(make_wall([-8, 3.4, -8], [-7.4, 6, -8]))    # 高台左牆
walls.append(make_wall([7.4, 3.4, -8], [8, 6, -8]))      # 高台右牆
walls.append(make_wall([-8, 3.4, 7.4], [8, 6, 8]))       # 高台後牆
walls.append(make_wall([-8, 3.4, -8], [-8, 6, -7.4]))    # 高台前牆左
walls.append(make_wall([7.4, 3.4, -8], [8, 6, -7.4]))    # 高台前牆右

# === 坡道（連接高低差）===
# 左坡道（從地面到高台）
walls.append(make_wall([-12, 0, -4], [-8, 0.3, 4]))       # 坡道底部
walls.append(make_wall([-12, 0.3, -4], [-8, 0.6, 4]))     # 坡道中段
walls.append(make_wall([-12, 0.6, -4], [-8, 0.9, 4]))     # 坡道中段2
walls.append(make_wall([-12, 0.9, -4], [-8, 1.2, 4]))     # 坡道中段3
walls.append(make_wall([-12, 1.2, -4], [-8, 1.5, 4]))     # 坡道中段4
walls.append(make_wall([-12, 1.5, -4], [-8, 1.8, 4]))     # 坡道中段5
walls.append(make_wall([-12, 1.8, -4], [-8, 2.1, 4]))     # 坡道中段6
walls.append(make_wall([-12, 2.1, -4], [-8, 2.4, 4]))     # 坡道中段7
walls.append(make_wall([-12, 2.4, -4], [-8, 2.7, 4]))     # 坡道中段8
walls.append(make_wall([-12, 2.7, -4], [-8, 3.0, 4]))     # 坡道頂部

# 右坡道
walls.append(make_wall([8, 0, -4], [12, 0.3, 4]))
walls.append(make_wall([8, 0.3, -4], [12, 0.6, 4]))
walls.append(make_wall([8, 0.6, -4], [12, 0.9, 4]))
walls.append(make_wall([8, 0.9, -4], [12, 1.2, 4]))
walls.append(make_wall([8, 1.2, -4], [12, 1.5, 4]))
walls.append(make_wall([8, 1.5, -4], [12, 1.8, 4]))
walls.append(make_wall([8, 1.8, -4], [12, 2.1, 4]))
walls.append(make_wall([8, 2.1, -4], [12, 2.4, 4]))
walls.append(make_wall([8, 2.4, -4], [12, 2.7, 4]))
walls.append(make_wall([8, 2.7, -4], [12, 3.0, 4]))

# === A 站點（左側）===
sites.append(make_site("A", [-20, 0, 15], 3.0))
# A 站點掩體
walls.append(make_wall([-24, 0, 12], [-18, 1.5, 13.5]))   # A 後牆
walls.append(make_wall([-24, 0, 16.5], [-18, 1.5, 18]))   # A 前牆
walls.append(make_wall([-24, 0, 12], [-23.5, 2.0, 18]))   # A 左牆
walls.append(make_wall([-18, 0, 12], [-17.5, 2.0, 18]))   # A 右牆
# A 站點內掩體
walls.append(make_wall([-22, 0, 14], [-20, 1.0, 16]))     # A 中央箱子
walls.append(make_wall([-19, 0, 13], [-17.5, 1.2, 15]))   # A 右側掩體

# === B 站點（中央）===
sites.append(make_site("B", [0, 0, 20], 3.0))
# B 站點掩體
walls.append(make_wall([-5, 0, 18], [5, 1.5, 19.5]))      # B 後牆
walls.append(make_wall([-5, 0, 20.5], [5, 1.5, 22]))      # B 前牆
walls.append(make_wall([-5, 0, 18], [-4.5, 2.5, 22]))     # B 左牆
walls.append(make_wall([4.5, 0, 18], [5, 2.5, 22]))       # B 右牆
# B 站點內掩體
walls.append(make_wall([-2, 0, 19], [2, 1.2, 21]))        # B 中央平台
walls.append(make_wall([-4, 0, 20], [-2.5, 0.8, 21.5]))   # B 左側掩體
walls.append(make_wall([2.5, 0, 20], [4, 0.8, 21.5]))     # B 右側掩體

# === C 站點（右側）===
sites.append(make_site("C", [20, 0, 15], 3.0))
# C 站點掩體
walls.append(make_wall([18, 0, 12], [24, 1.5, 13.5]))     # C 後牆
walls.append(make_wall([18, 0, 16.5], [24, 1.5, 18]))     # C 前牆
walls.append(make_wall([18, 0, 12], [17.5, 2.0, 18]))     # C 左牆
walls.append(make_wall([23.5, 0, 12], [24, 2.0, 18]))     # C 右牆
# C 站點內掩體
walls.append(make_wall([19, 0, 14], [21, 1.0, 16]))       # C 中央箱子
walls.append(make_wall([21, 0, 13], [22.5, 1.2, 15]))     # C 左側掩體

# === 通道掩體（連接各區域）===
# 左通道（A → 中央）
walls.append(make_wall([-16, 0, -12], [-14, 1.5, -8]))     # 左通道牆
walls.append(make_wall([-16, 0, 8], [-14, 1.5, 12]))       # 左通道牆2

# 右通道（C → 中央）
walls.append(make_wall([14, 0, -12], [16, 1.5, -8]))       # 右通道牆
walls.append(make_wall([14, 0, 8], [16, 1.5, 12]))         # 右通道牆2

# 中央通道（A → B → C）
walls.append(make_wall([-8, 0, 14], [-6, 1.5, 18]))        # 中左牆
walls.append(make_wall([6, 0, 14], [8, 1.5, 18]))          # 中右牆

# === 裝飾性掩體 ===
# 角落柱子
for pos in [(-25, -25), (25, -25), (-25, 25), (25, 25)]:
    walls.append(make_wall([pos[0]-0.8, 0, pos[1]-0.8], [pos[0]+0.8, 3.0, pos[1]+0.8]))

# 中央高台周圍護欄
walls.append(make_wall([-8, 3, -10], [8, 4.5, -9.5]))      # 前護欄
walls.append(make_wall([-10, 3, -8], [-9.5, 4.5, 8]))       # 左護欄
walls.append(make_wall([9.5, 3, -8], [10, 4.5, 8]))         # 右護欄

# === 重生點 ===
# 攻方（地圖北側，z < 0）
spawns_a = [
    make_spawn(-20, -25),
    make_spawn(-15, -25),
    make_spawn(-10, -25),
    make_spawn(-5, -25),
    make_spawn(0, -25),
]

# 守方（地圖南側，z > 0）
spawns_d = [
    make_spawn(-20, 25),
    make_spawn(-15, 25),
    make_spawn(-10, 25),
    make_spawn(-5, 25),
    make_spawn(0, 25),
]

# === 組裝地圖 ===
map_data = {
    "bounds_min": {"x": -30, "y": 0, "z": -30},
    "bounds_max": {"x": 30, "y": 8, "z": 30},
    "walls": walls,
    "sites": sites,
    "spawns_attackers": spawns_a,
    "spawns_defenders": spawns_d,
}

# 輸出
print(json.dumps(map_data, indent=2))
