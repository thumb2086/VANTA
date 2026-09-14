"""
server/core/rs_bridge.py — Rust 核心擴展載入橋接
==================================================
載入 vanta_core_rs（PyO3 編譯的 C 擴展）。找不到擴展時回退純 Python：
  * RustMovementController — 鏡像 MovementController 的完整介面
  * RustRecoilController  — 種子化後座力控制器
  * rust_resolve_hitscan   — 彈道解析（純函式）
確定性：Rust 核心與 Python 核心位元組級一致（parity 測試鎖定），
因此「換核心」不改變任何行為，只改變效能。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os

from server.core.math_core import Vec3
from server.core.movement import MovementConfig

_RUST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_rust")
_PROJECT_RUST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "rust", "vanta_core_rs", "target", "release")

_SO_CANDIDATES = (
    os.path.join(_RUST_DIR, "vanta_core_rs.so"),
    os.path.join(_RUST_DIR, "libvanta_core_rs.so"),
    os.path.join(_PROJECT_RUST, "libvanta_core_rs.so"),
)

_rs = None
_tried = False


def _load():
    """載入 Rust 擴展（只嘗試一次）。回傳模組或 None。"""
    global _rs, _tried
    if _tried:
        return _rs
    _tried = True
    for path in _SO_CANDIDATES:
        if os.path.isfile(path):
            try:
                loader = importlib.machinery.ExtensionFileLoader("vanta_core_rs", path)
                spec = importlib.util.spec_from_loader("vanta_core_rs", loader)
                mod = importlib.util.module_from_spec(spec)
                loader.exec_module(mod)
                _rs = mod
                break
            except Exception:
                continue
    return _rs


def rs_available() -> bool:
    return _load() is not None


def force_python() -> None:
    """強制回退純 Python（測試用）。"""
    global _rs, _tried
    _rs = None
    _tried = True


def _cfg_dict(cfg: MovementConfig | None) -> dict | None:
    if cfg is None:
        return None
    return {
        "run_speed": cfg.run_speed,
        "walk_ratio": cfg.walk_ratio,
        "crouch_ratio": cfg.crouch_ratio,
        "jump_speed": cfg.jump_speed,
        "gravity": cfg.gravity,
        "ground_accel": cfg.ground_accel,
        "ground_friction": cfg.ground_friction,
        "opposite_decel": cfg.opposite_decel,
        "air_accel": cfg.air_accel,
        "air_speed_ratio": cfg.air_speed_ratio,
        "jump_buffer_time": cfg.jump_buffer_time,
        "jump_coyote_time": cfg.jump_coyote_time,
    }


class RustMovementController:
    """以 Rust 核心實作的 MovementController（鏡像 Python 介面）。"""

    def __init__(self, cfg: MovementConfig | None = None, ground_y: float = 0.0):
        self._cfg = cfg if cfg is not None else MovementConfig()
        self._inner = _load().MovementController(_cfg_dict(self._cfg), ground_y)

    # --- 介面（對齊 MovementController）---
    @property
    def pos(self) -> Vec3:
        x, y, z = self._inner.pos
        return Vec3(x, y, z)

    @pos.setter
    def pos(self, v: Vec3) -> None:
        self._inner.set_pos(v.x, v.y, v.z)

    @property
    def vel(self) -> Vec3:
        x, y, z = self._inner.vel
        return Vec3(x, y, z)

    @vel.setter
    def vel(self, v: Vec3) -> None:
        self._inner.set_vel(v.x, v.y, v.z)

    @property
    def on_ground(self) -> bool:
        return self._inner.on_ground

    @property
    def crouching(self) -> bool:
        return self._inner.crouching

    @property
    def walking(self) -> bool:
        return self._inner.walking

    @property
    def time_since_land(self) -> float:
        return self._inner.time_since_land

    def step(self, inp, dt: float, speed_mult: float = 1.0) -> None:
        self._inner.step(inp.forward, inp.strafe, inp.walk, inp.crouch, inp.jump,
                         dt, speed_mult)

    def current_max_speed(self) -> float:
        return self._inner.current_max_speed()

    def horizontal_speed(self) -> float:
        return self._inner.horizontal_speed()

    def speed_ratio(self) -> float:
        return self._inner.speed_ratio()


class RustMovementBatch:
    """批次移動：一次跨邊界處理 N 玩家 × 多步（攤平 pyo3 邊界成本）。"""

    def __init__(self, cfg: MovementConfig | None = None, ground_y: float = 0.0,
                 count: int = 10):
        self._count = count
        self._inner = _load().MovementBatch(_cfg_dict(cfg), ground_y, count)

    def step_all(self, fwd, strafe, walk, crouch, jump, speed_mult, dt: float) -> None:
        self._inner.step_all(fwd, strafe, walk, crouch, jump, speed_mult, dt)

    def positions(self) -> list:
        return self._inner.positions()

    def velocities(self) -> list:
        return self._inner.velocities()

    def set_state(self, i, px, py, pz, vx, vy, vz) -> None:
        self._inner.set_state(i, px, py, pz, vx, vy, vz)


class RustWorldSim:
    """世界迴圈 Rust 化（M4）：一次跨邊界完成 N 玩家移動 + 碰撞。"""

    def __init__(self, walls, cfg: MovementConfig | None = None, ground_y: float = 0.0,
                 count: int = 10):
        # walls: [(mn_x, mn_y, mn_z, mx_x, mx_y, mx_z), ...]
        self._count = count
        self._inner = _load().WorldSim(list(walls), _cfg_dict(cfg), ground_y, count)

    def sync_states(self, pos, vel) -> None:
        """每 tick Python→Rust 位置/速度同步（重生/回彈尊重）。"""
        self._inner.sync_states(pos, vel)

    def step_all(self, fwd, strafe, walk, crouch, jump, speed_mult, alive,
                 dt: float, movable: bool) -> None:
        self._inner.step_all(fwd, strafe, walk, crouch, jump, speed_mult, alive, dt, movable)

    def positions(self) -> list:
        return self._inner.positions()

    def velocities(self) -> list:
        return self._inner.velocities()

    def on_grounds(self) -> list:
        return self._inner.on_grounds()

    def crouchings(self) -> list:
        return self._inner.crouchings()

    def walkings(self) -> list:
        return self._inner.walkings()

    def time_since_lands(self) -> list:
        return self._inner.time_since_lands()


class RustRecoilController:
    """以 Rust 核心實作的後座力控制器（種子化）。"""

    def __init__(self, seed: int = 42):
        self._inner = _load().RecoilController(seed)

    def fire(self, now: float) -> tuple[float, float]:
        return self._inner.fire(now)

    def update(self, now: float, dt: float) -> None:
        self._inner.update(now, dt)

    @property
    def pitch(self) -> float:
        return self._inner.pitch

    @property
    def yaw(self) -> float:
        return self._inner.yaw

    @property
    def bullet_index(self) -> int:
        return self._inner.bullet_index

    @property
    def shots_fired(self) -> int:
        return self._inner.shots_fired


def rust_resolve_hitscan(players, walls, shooter, origin, target, damage,
                         pen_level, max_dist=150.0):
    """Rust 彈道解析。players/walls 為 list of tuples；target 為瞄準目標點。"""
    return _load().resolve_hitscan(players, walls, shooter, origin, target,
                                   damage, pen_level, max_dist)
