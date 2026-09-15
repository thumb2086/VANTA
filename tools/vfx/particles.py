"""
tools/vfx/particles.py — 可程式化粒子特效（v2）
=============================================
粒子發射器定義（資料驅動）：
  * 發射器型態：point（爆發）/ cone（錐形噴射）/ sphere（散佈）/ directional
  * 粒子參數：數量、速度、壽命、大小、重力、空氣阻力、顏色漸變、拖尾、加法混合
  * v2 新增：貼圖精靈、尺寸／透明度曲線、自轉、渦流擾動、速度對齊與拉伸、
             發光倍率、動態光源、命中貼花（decal）、子發射器（死亡觸發）

提供預設特效（火花/彈殼/爆炸/煙霧/血花/命中標記/曳光/擊殺確認），
並由 `tools.vfx.styles` 展開 12+ 種「槍皮風格」蓝图，
以「確定性模擬」產生關鍵幀（供渲染層直接使用或除錯、也供網頁展示台播放）。
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
    # ── v2：進階外观／行為（皆有預設值，向後相容）──
    sprite: str = ""                    # 關聯貼圖名（tools/vfx/sprites）
    size_curve: tuple = ()              # (起, 中, 末) 尺寸乘子；空 → 線性收斂
    alpha_curve: tuple = ()             # (起, 中, 末) 透明度；空 → 1→0 線性
    spin: float = 0.0                   # 自轉速度（度/秒）
    turbulence: float = 0.0             # 每步隨機速度擾動強度
    stretch: float = 0.0                # 依速度拉伸（曳光用），0=不拉伸
    emissive: float = 1.0               # 發光倍率（渲染層 → emission_energy）
    align: str = ""                     # "" / "velocity"（面向速度向量）
    light: dict = field(default_factory=dict)      # {color, energy, range, lifetime}
    decal: str = ""                     # 命中貼花（tools/vfx/decals）
    sub: str = ""                        # 死亡時觸發的子發射器
    loop: bool = False                  # 循環播放（環境特效）
    attach: str = "world"               # world / muzzle / weapon / camera
    banner: str = ""                     # 擊殺橫幅樣式（供 HUD 使用）
    budget: int = 1                      # 效能預算級（1=便宜, 3=昂貴）


PRESETS: dict[str, ParticleEmitter] = {
    "muzzle_flash": ParticleEmitter("muzzle_flash", "cone", 8, 8.0, 0.3, 0.12, 0.3, 0.08, 0.3,
                                    0.0, 2.0, (255, 240, 160), (255, 120, 40), True, True,
                                    direction=(0.0, 0.0, 1.0), cone_angle=20.0),
    "shell_casing": ParticleEmitter("shell_casing", "directional", 1, 3.0, 0.5, 1.2, 0.2, 0.03, 0.2,
                                    GRAVITY, 0.0, (200, 170, 90), (140, 110, 50), False, False,
                                    direction=(0.3, 1.0, 0.1), spin=420.0),
    # 火花：初速快、阻力強、壽命短——重力要壓得過初速，否則會看到「往上飄的火花」
    "spark": ParticleEmitter("spark", "sphere", 24, 6.5, 0.5, 0.42, 0.4, 0.05, 0.4,
                             16.0, 4.5, (255, 255, 200), (255, 80, 30), True, True, radius=0.4),
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

    # ═══════════════════════════════════════════════════════════
    # v2：分层／命中／環境特效（客戶端 FxManager 直接消費）
    # ═══════════════════════════════════════════════════════════
    "muzzle_core": ParticleEmitter("muzzle_core", "cone", 1, 0.0, 0.0, 0.06, 0.0, 0.34, 0.12,
                                   0.0, 0.0, (255, 250, 225), (255, 190, 90), True, False,
                                   direction=(0.0, 0.0, 1.0), sprite="sprite_flare",
                                   size_curve=(0.55, 1.15, 0.0), emissive=6.0, budget=1),
    "muzzle_smoke": ParticleEmitter("muzzle_smoke", "cone", 6, 1.6, 0.5, 0.55, 0.4, 0.16, 0.5,
                                    -0.35, 1.8, (120, 118, 116), (40, 40, 42), False, False,
                                    direction=(0.0, 0.0, 1.0), cone_angle=28.0,
                                    sprite="sprite_smoke", alpha_curve=(0.0, 0.5, 0.0),
                                    size_curve=(0.5, 1.0, 2.1)),
    "muzzle_sparks": ParticleEmitter("muzzle_sparks", "cone", 10, 13.0, 0.55, 0.28, 0.4, 0.02, 0.4,
                                     7.5, 1.2, (255, 236, 180), (255, 110, 30), True, True,
                                     direction=(0.0, 0.0, 1.0), cone_angle=32.0,
                                     sprite="sprite_spark", stretch=0.9, emissive=3.0),
    "impact_wall": ParticleEmitter("impact_wall", "cone", 14, 6.0, 0.5, 0.34, 0.25, 0.045, 0.5,
                                   6.0, 2.2, (240, 232, 210), (150, 130, 110), True, False,
                                   direction=(0.0, 1.0, 0.0), cone_angle=68.0,
                                   sprite="sprite_dust", decal="bullet_hole", alpha_curve=(0, .7, 0)),
    "impact_metal": ParticleEmitter("impact_metal", "cone", 16, 9.0, 0.6, 0.3, 0.25, 0.03, 0.5,
                                    8.0, 1.6, (255, 246, 200), (255, 120, 40), True, True,
                                    direction=(0.0, 1.0, 0.0), cone_angle=78.0,
                                    sprite="sprite_spark", emissive=3.0, decal="ricochet_mark"),
    "impact_flesh": ParticleEmitter("impact_flesh", "cone", 14, 4.6, 0.55, 0.42, 0.3, 0.05, 0.5,
                                    9.0, 2.0, (190, 30, 34), (70, 6, 10), False, False,
                                    direction=(0.0, 1.0, 0.0), cone_angle=58.0,
                                    sprite="sprite_glob", decal="blood_spatter", budget=2),
    "impact_glass": ParticleEmitter("impact_glass", "sphere", 22, 7.0, 0.6, 0.5, 0.4, 0.04, 0.6,
                                    8.5, 1.0, (215, 240, 255), (120, 170, 210), True, False,
                                    sprite="sprite_shard", spin=260.0, decal="glass_crack"),
    "ricochet": ParticleEmitter("ricochet", "cone", 12, 12.0, 0.7, 0.34, 0.35, 0.02, 0.5,
                                9.0, 0.6, (255, 240, 190), (255, 90, 30), True, True,
                                direction=(0.0, 1.0, 0.0), cone_angle=64.0, sprite="sprite_spark",
                                stretch=1.4, emissive=3.0),
    "headshot_shatter": ParticleEmitter("headshot_shatter", "sphere", 30, 8.5, 0.6, 0.55, 0.4, 0.06, 0.5,
                                        9.5, 1.2, (255, 245, 210), (200, 60, 40), True, True,
                                        sprite="sprite_shard", spin=320.0, budget=2),
    "blood_mist": ParticleEmitter("blood_mist", "sphere", 18, 2.6, 0.6, 0.85, 0.4, 0.10, 0.5,
                                  5.5, 2.4, (150, 22, 26), (60, 6, 10), False, False,
                                  sprite="sprite_smoke", alpha_curve=(0.0, 0.55, 0.0), radius=0.35),
    "dash_trail": ParticleEmitter("dash_trail", "sphere", 26, 1.2, 0.4, 0.42, 0.35, 0.13, 0.4,
                                  -0.4, 2.4, (150, 215, 255), (40, 70, 150), True, True,
                                  sprite="sprite_smoke", alpha_curve=(0.45, 0.35, 0.0),
                                  loop=True, attach="weapon", budget=2),
    "spike_pulse": ParticleEmitter("spike_pulse", "cone", 12, 1.6, 0.3, 1.0, 0.3, 0.05, 0.4,
                                   -0.6, 1.4, (255, 90, 60), (120, 20, 10), True, False,
                                   direction=(0.0, 1.0, 0.0), cone_angle=18.0,
                                   sprite="sprite_glow", loop=True, emissive=3.0,
                                   light={"color": "#ff5a3a", "energy": 2.2, "range": 4.0,
                                          "lifetime": 1.0}),
    "spike_shockwave": ParticleEmitter("spike_shockwave", "sphere", 90, 26.0, 0.35, 1.15, 0.25,
                                       0.3, 0.4, 1.5, 1.2, (255, 235, 190), (190, 60, 20),
                                       True, True, sprite="sprite_flame", stretch=0.6,
                                       emissive=5.0, budget=3,
                                       light={"color": "#ff8a3a", "energy": 12.0, "range": 26.0,
                                              "lifetime": 0.5}),
    "flash_pop": ParticleEmitter("flash_pop", "sphere", 24, 9.0, 0.4, 0.35, 0.2, 0.22, 0.5,
                                 0.0, 3.0, (255, 255, 255), (210, 230, 255), True, False,
                                 sprite="sprite_glow", size_curve=(0.2, 1.6, 0.0), emissive=8.0,
                                 light={"color": "#ffffff", "energy": 10.0, "range": 12.0,
                                        "lifetime": 0.25}),
    "smoke_bloom": ParticleEmitter("smoke_bloom", "sphere", 40, 2.2, 0.5, 4.2, 0.5, 0.9, 0.4,
                                   -0.25, 1.1, (150, 155, 165), (70, 74, 82), False, False,
                                   sprite="sprite_smoke", radius=1.6, loop=True,
                                   alpha_curve=(0.0, 0.85, 0.7), budget=2),
    "ember_float": ParticleEmitter("ember_float", "sphere", 22, 1.1, 0.6, 2.4, 0.5, 0.03, 0.5,
                                   -1.1, 0.8, (255, 170, 70), (150, 40, 10), True, True,
                                   sprite="sprite_spark", loop=True, attach="world"),
    "trap_glow": ParticleEmitter("trap_glow", "cone", 10, 1.4, 0.4, 1.6, 0.4, 0.04, 0.5,
                                 -0.5, 1.5, (255, 130, 60), (140, 30, 20), True, False,
                                 direction=(0.0, 1.0, 0.0), cone_angle=22.0, sprite="sprite_glow",
                                 loop=True, emissive=2.6),
    "heal_aura": ParticleEmitter("heal_aura", "sphere", 20, 1.4, 0.5, 1.6, 0.4, 0.06, 0.5,
                                 -1.6, 1.0, (130, 255, 190), (40, 150, 110), True, False,
                                 sprite="sprite_star4", radius=0.5, loop=True, emissive=2.4),
    "shield_ring": ParticleEmitter("shield_ring", "cone", 26, 3.0, 0.3, 0.9, 0.3, 0.05, 0.4,
                                   0.0, 1.2, (120, 190, 255), (30, 70, 190), True, False,
                                   direction=(0.0, 1.0, 0.0), cone_angle=90.0,
                                   sprite="sprite_ring", loop=True, emissive=2.2),
    "banner_sparkle": ParticleEmitter("banner_sparkle", "point", 18, 2.2, 0.6, 0.45, 0.3, 0.03, 0.6,
                                      0.4, 2.6, (255, 240, 190), (255, 140, 60), True, True,
                                      sprite="sprite_star4", attach="camera", emissive=3.0),
}


def _register_styles() -> None:
    """把 `tools/vfx/styles.py` 的風格模板展開成 ParticleEmitter 並註冊。"""
    from tools.vfx import styles

    for style, slots in styles.STYLE_PRESETS.items():
        for slot, params in slots.items():
            name = f"{slot}_{style}"
            if name in PRESETS:
                continue
            kw = dict(params)
            sub = kw.get("sub", "")
            if isinstance(sub, str) and sub.startswith("smoke_") and sub not in PRESETS:
                kw["sub"] = f"smoke_{style}"          # 子發射器指向同風格煙霧
            PRESETS[name] = ParticleEmitter(name, **kw)


_register_styles()


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
        # v2
        "sprite": e.sprite, "size_curve": list(e.size_curve), "alpha_curve": list(e.alpha_curve),
        "spin": e.spin, "turbulence": e.turbulence, "stretch": e.stretch,
        "emissive": e.emissive, "align": e.align, "light": dict(e.light),
        "decal": e.decal, "sub": e.sub, "loop": e.loop, "attach": e.attach,
        "banner": e.banner, "budget": e.budget,
    }


def preset_dict(name: str) -> dict:
    """取得蓝图的 dict 形式（工具鏈輸出用）。"""
    return to_dict(preset(name))


def style_of(name: str) -> str:
    """由蓝图名推回風格（`muzzle_soul` → `soul`；未知 → default）。"""
    from tools.vfx import styles
    for style in styles.STYLE_PRESETS:
        if name.endswith("_" + style):
            return style
    return "default"


def validate_presets() -> list[str]:
    """所有蓝图互相引用（sub）與曲線長度是否合法。"""
    issues: list[str] = []
    for name, e in PRESETS.items():
        if e.sub and e.sub not in PRESETS:
            issues.append(f"{name}: 子發射器不存在 {e.sub}")
        for label, curve in (("size_curve", e.size_curve), ("alpha_curve", e.alpha_curve)):
            if curve and len(curve) not in (2, 3):
                issues.append(f"{name}: {label} 需要 2 或 3 個關鍵點")
        if e.count <= 0:
            issues.append(f"{name}: count 必須 > 0")
        if e.life <= 0:
            issues.append(f"{name}: life 必須 > 0")
        if not (0 <= e.budget <= 3):
            issues.append(f"{name}: budget 需介於 0..3")
    return issues


# --------------------------------------------------------------------- #
# 確定性關鍵幀模擬（供渲染層/除錯/網頁展示台播放）
# --------------------------------------------------------------------- #
def animate_frames(e: ParticleEmitter, seed: int = 0, fps: int = 60,
                   duration: float | None = None) -> list[dict]:
    """模擬粒子系統，輸出每幀的粒子狀態（確定性）。

    回傳：[{t, particles: [{pos:[x,y,z], size, color:[r,g,b], alpha, rot}]}, ...]
    """
    rng = random.Random(seed)
    dt = 1.0 / fps
    total = duration or e.life * 1.3

    particles = []
    for _ in range(e.count):
        life = max(0.05, e.life * rng.uniform(1 - e.life_var, 1 + e.life_var))
        speed = e.speed * rng.uniform(1 - e.speed_var, 1 + e.speed_var)
        size = max(0.01, e.size * rng.uniform(1 - e.size_var, 1 + e.size_var))
        if e.kind in ("point", "sphere"):
            dirv = _random_dir(rng)
        elif e.kind == "directional":
            dirv = _norm(e.direction)
        else:  # cone
            dirv = _cone_dir(rng, e.direction, e.cone_angle)
        vel = tuple(v * speed for v in dirv)
        pos = (0.0, 0.0, 0.0)
        if e.kind == "sphere":
            pos = tuple(rng.uniform(-e.radius, e.radius) for _ in range(3))
        particles.append({
            "vel": list(vel), "pos": list(pos), "life": life, "age": 0.0, "size": size,
            "rot": rng.uniform(0.0, 360.0),
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
            pos = p["pos"]
            vel = p["vel"]
            pos[0] += vel[0] * dt
            pos[1] += vel[1] * dt
            pos[2] += vel[2] * dt
            vel[1] -= e.gravity * dt
            if e.drag > 0:
                drag = max(0.0, 1.0 - e.drag * dt)
                vel[0] *= drag
                vel[1] *= drag
                vel[2] *= drag
            if e.turbulence > 0:
                k = e.turbulence * dt
                vel[0] += rng.uniform(-k, k)
                vel[1] += rng.uniform(-k, k)
                vel[2] += rng.uniform(-k, k)
            u = min(1.0, age / p["life"])
            color = [_lerp(e.color_start[i], e.color_end[i], u) for i in range(3)]
            alpha = _curve(e.alpha_curve, u, 1.0 - u)
            size = p["size"] * _curve(e.size_curve, u, 1.0 - 0.6 * u)
            entry = {
                "pos": [round(v, 3) for v in pos],
                "size": round(size, 3),
                "color": [round(c, 0) for c in color],
                "alpha": round(alpha, 3),
            }
            if e.spin:
                p["rot"] = (p["rot"] + e.spin * dt) % 360.0
                entry["rot"] = round(p["rot"], 2)
            if e.stretch:
                vlen = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)
                entry["stretch"] = round(1.0 + vlen * e.stretch * 0.05, 3)
            if e.align == "velocity":
                entry["dir"] = [round(v, 3) for v in _norm(vel)]
            frame_particles.append(entry)
        frames.append({"t": round(t, 3), "particles": frame_particles})
    return frames


def _curve(curve: tuple, u: float, fallback: float) -> float:
    """2/3 關鍵點曲線插值；無曲線時退回 fallback。"""
    if not curve:
        return fallback
    n = len(curve)
    if n == 2:
        return _lerp(curve[0], curve[1], u)
    seg = u * 2.0
    if seg <= 1.0:
        return _lerp(curve[0], curve[1], seg)
    return _lerp(curve[1], curve[2], seg - 1.0)


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
