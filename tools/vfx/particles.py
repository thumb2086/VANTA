"""
tools/vfx/particles.py — 可程式化粒子特效
=========================================
粒子發射器定義（資料驅動）：
  * 發射器型態：point（爆發）/ cone（錐形噴射）/ sphere（散佈）/ directional
  * 粒子參數：數量、速度、壽命、大小、重力、顏色漸變、拖尾、加法混合
提供預設特效（火花/彈殼/爆炸/煙霧/血花/命中標記/曳光/擊殺確認），
並以「確定性模擬」產生關鍵幀（供渲染層直接使用或除錯）。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

GRAVITY = 9.8


@dataclass(slots=True)
class ParticleEmitter:
    name: str
    kind: str = "point"                # point / cone / sphere / directional
    count: int = 20
    speed: float = 6.0
    speed_var: float = 0.4
    life: float = 0.6
    life_var: float = 0.3
    size: float = 0.1
    size_var: float = 0.3
    gravity: float = 0.0
    drag: float = 0.0
    color_start: tuple = (255, 220, 120)
    color_end: tuple = (120, 40, 20)
    additive: bool = True
    trail: bool = False
    direction: tuple = (0.0, 1.0, 0.0)  # cone 軸向
    cone_angle: float = 45.0
    radius: float = 0.5                 # sphere 半徑


PRESETS: dict[str, ParticleEmitter] = {
    "muzzle_flash": ParticleEmitter("muzzle_flash", "cone", 8, 8.0, 0.3, 0.12, 0.3, 0.08, 0.3,
                                    0.0, 2.0, (255, 240, 160), (255, 120, 40), True, True,
                                    direction=(0.0, 0.0, 1.0), cone_angle=20.0),
    "shell_casing": ParticleEmitter("shell_casing", "directional", 1, 3.0, 0.5, 1.2, 0.2, 0.03, 0.2,
                                    GRAVITY, 0.0, (200, 170, 90), (140, 110, 50), False, False,
                                    direction=(0.3, 1.0, 0.1)),
    "spark": ParticleEmitter("spark", "sphere", 24, 9.0, 0.5, 0.5, 0.4, 0.05, 0.4,
                             2.0, 3.0, (255, 255, 200), (255, 80, 30), True, True, radius=0.4),
    "explosion_debris": ParticleEmitter("explosion_debris", "sphere", 40, 14.0, 0.6, 0.9, 0.4, 0.15, 0.4,
                                        GRAVITY, 1.5, (255, 200, 100), (80, 40, 20), True, True, radius=1.0),
    "smoke_puff": ParticleEmitter("smoke_puff", "sphere", 18, 2.5, 0.5, 3.5, 0.4, 1.0, 0.5,
                                  -0.5, 1.0, (180, 180, 180), (90, 90, 90), False, False, radius=0.8),
    "blood": ParticleEmitter("blood", "sphere", 16, 4.0, 0.5, 0.7, 0.3, 0.06, 0.3,
                             GRAVITY, 2.0, (180, 20, 20), (90, 10, 10), False, False, radius=0.3),
    "hit_marker": ParticleEmitter("hit_marker", "point", 6, 0.0, 0.0, 0.25, 0.0, 0.03, 0.0,
                                  0.0, 0.0, (255, 255, 255), (255, 255, 255), True, False),
    "tracer": ParticleEmitter("tracer", "directional", 1, 60.0, 0.05, 0.08, 0.1, 0.02, 0.2,
                              0.0, 0.0, (255, 250, 180), (255, 200, 80), True, True,
                              direction=(0.0, 0.0, 1.0)),
    "kill_confirm": ParticleEmitter("kill_confirm", "sphere", 30, 5.0, 0.5, 0.8, 0.3, 0.08, 0.3,
                                    -1.0, 1.5, (255, 220, 100), (255, 60, 60), True, True, radius=0.6),
}


def preset(name: str) -> ParticleEmitter:
    if name not in PRESETS:
        raise KeyError(f"unknown vfx preset: {name}")
    return PRESETS[name]


def to_dict(e: ParticleEmitter) -> dict:
    return {
        "name": e.name, "kind": e.kind, "count": e.count,
        "speed": e.speed, "speed_var": e.speed_var, "life": e.life, "life_var": e.life_var,
        "size": e.size, "size_var": e.size_var, "gravity": e.gravity, "drag": e.drag,
        "color_start": list(e.color_start), "color_end": list(e.color_end),
        "additive": e.additive, "trail": e.trail,
        "direction": list(e.direction), "cone_angle": e.cone_angle, "radius": e.radius,
    }


# --------------------------------------------------------------------- #
# 確定性關鍵幀模擬（供渲染層/除錯）
# --------------------------------------------------------------------- #
def animate_frames(e: ParticleEmitter, seed: int = 0, fps: int = 60,
                   duration: float | None = None) -> list[dict]:
    """模擬粒子系統，輸出每幀的粒子狀態（確定性）。

    回傳：[{t, particles: [{pos:[x,y,z], size, color:[r,g,b], alpha}]}, ...]
    """
    rng = random.Random(seed)
    dt = 1.0 / fps
    total = duration or e.life * 1.3

    # 生成粒子（生命/速度/方向）
    particles = []
    for _ in range(e.count):
        life = max(0.05, e.life * rng.uniform(1 - e.life_var, 1 + e.life_var))
        speed = e.speed * rng.uniform(1 - e.speed_var, 1 + e.speed_var)
        size = max(0.01, e.size * rng.uniform(1 - e.size_var, 1 + e.size_var))
        if e.kind == "point":
            dirv = _random_dir(rng)
        elif e.kind == "sphere":
            dirv = _random_dir(rng)
        elif e.kind == "directional":
            dirv = e.direction
        else:  # cone
            dirv = _cone_dir(rng, e.direction, e.cone_angle)
        vel = tuple(v * speed for v in dirv)
        pos = (0.0, 0.0, 0.0)
        if e.kind == "sphere":
            pos = tuple(rng.uniform(-e.radius, e.radius) for _ in range(3))
        particles.append({
            "vel": list(vel), "pos": list(pos), "life": life, "age": 0.0, "size": size,
        })

    frames = []
    n_frames = int(total / dt)
    for f in range(n_frames):
        t = f * dt
        frame_particles = []
        for p in particles:
            age = p["age"] + dt
            if age > p["life"]:
                continue
            p["age"] = age
            # 積分（顯式歐拉）
            pos = p["pos"]
            vel = p["vel"]
            pos[0] += vel[0] * dt
            pos[1] += vel[1] * dt
            pos[2] += vel[2] * dt
            vel[1] -= e.gravity * dt
            if e.drag > 0:
                drag = max(0.0, 1.0 - e.drag * dt)
                vel[0] *= drag; vel[1] *= drag; vel[2] *= drag
            # 顏色/透明度插值
            u = min(1.0, age / p["life"])
            color = [_lerp(e.color_start[i], e.color_end[i], u) for i in range(3)]
            alpha = 1.0 - u
            frame_particles.append({
                "pos": [round(v, 3) for v in p["pos"]],
                "size": round(p["size"], 3),
                "color": [round(c, 0) for c in color],
                "alpha": round(alpha, 3),
            })
        frames.append({"t": round(t, 3), "particles": frame_particles})
    return frames


def _random_dir(rng) -> tuple:
    """均勻單位球方向。"""
    z = rng.uniform(-1, 1)
    phi = rng.uniform(0, math.tau)
    r = math.sqrt(max(0.0, 1 - z * z))
    return (r * math.cos(phi), z, r * math.sin(phi))


def _cone_dir(rng, axis, angle_deg) -> tuple:
    """以 axis 為軸的錐形方向。"""
    ang = math.radians(angle_deg) * rng.random()
    phi = rng.uniform(0, math.tau)
    ax = _norm(axis)
    perp1 = _norm((ax[1], -ax[0], 0.0)) if abs(ax[0]) > 0.1 or abs(ax[1]) > 0.1 else (0.0, 0.0, 1.0)
    perp2 = _cross(ax, perp1)
    d = tuple(ax[i] * math.cos(ang) + (perp1[i] * math.cos(phi) + perp2[i] * math.sin(phi)) * math.sin(ang) for i in range(3))
    return _norm(d)


def _norm(v) -> tuple:
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v) if l > 1e-9 else (0.0, 1.0, 0.0)


def _cross(a, b) -> tuple:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u
