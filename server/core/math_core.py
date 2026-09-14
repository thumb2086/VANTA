"""
server/core/math_core.py — 純數學核心 (Pure Math Core)
======================================================
全伺服器共用的向量/數值工具。設計原則：
  1. 純函式 (pure functions)：相同輸入 → 完全相同輸出（確定性）。
  2. 統一使用 float64 (IEEE 754)，避免平台相依函式。
  3. 模擬順序固定（見 movement.MovementController.step 的 tick 順序註解）。

單位：長度 = 公尺 (m)、時間 = 秒 (s)、角度 = 度 (deg)。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EPSILON: float = 1e-12


@dataclass(frozen=True, slots=True)
class Vec3:
    """不可變三維向量。frozen + slots → 可雜湊、省記憶體、不可被客戶端篡改。"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec3":
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z

    def length(self) -> float:
        return math.sqrt(self.length_sq())

    def normalized(self) -> "Vec3":
        """回傳單位向量；零向量回傳零向量（呼叫端需自行判斷）。"""
        length = self.length()
        if length < EPSILON:
            return Vec3()
        return Vec3(self.x / length, self.y / length, self.z / length)

    def distance_to(self, other: "Vec3") -> float:
        return (self - other).length()

    def horizontal(self) -> "Vec3":
        """僅保留 XZ 平面分量（Y 歸零），供地面移動計算使用。"""
        return Vec3(self.x, 0.0, self.z)


def clamp(value: float, lo: float, hi: float) -> float:
    """將 value 夾取至 [lo, hi]。"""
    return lo if value < lo else hi if value > hi else value


def lerp(a: float, b: float, t: float) -> float:
    """線性插值 a→b，t ∈ [0,1]。"""
    return a + (b - a) * t


def approach(value: float, target: float, max_delta: float) -> float:
    """朝 target 逼近，每次最多改變 max_delta（框率無關的指數逼近）。"""
    diff = target - value
    if abs(diff) <= max_delta:
        return target
    return value + math.copysign(max_delta, diff)


def approach_vec(v: Vec3, target: Vec3, max_delta: float) -> Vec3:
    """向量版 approach：沿差值方向逼近，最多移動 max_delta。"""
    diff = target - v
    dist = diff.length()
    if dist <= max_delta or dist < EPSILON:
        return target
    return v + diff * (max_delta / dist)


def deg2rad(deg: float) -> float:
    return deg * math.pi / 180.0


def rad2deg(rad: float) -> float:
    return rad * 180.0 / math.pi


def dir_from_yaw_pitch(yaw_deg: float, pitch_deg: float) -> Vec3:
    """朝向角 → 單位方向向量。yaw 0° = +Z，正值向右；pitch 正值向上。"""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    return Vec3(
        math.sin(y) * math.cos(p),
        math.sin(p),
        math.cos(y) * math.cos(p),
    )


def yaw_pitch_from_dir(d: Vec3) -> tuple[float, float]:
    """單位方向向量 → (yaw_deg, pitch_deg)。"""
    d = d.normalized()
    return (math.degrees(math.atan2(d.x, d.z)), math.degrees(math.asin(clamp(d.y, -1.0, 1.0))))
