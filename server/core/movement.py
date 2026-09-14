"""
server/core/movement.py — M1 自訂角色控制器 (Custom Character Controller)
======================================================================
目標：以「伺服器權威」為前提的高精度移動模擬，對齊《特戰英豪》移動模型
（社群量測值近似，全部為可調參數，見 docs/00_research_notes.md）：

  * 基礎跑速：手持步槍 ≈ 5.4 m/s（依武器重量類別調整，見 M4 武器資料庫）
  * 靜步 (Shift / Walk)：≈ 跑速 × 0.54   （約 2.9 m/s，特戰實測）
  * 下蹲 (Crouch)：      ≈ 跑速 × 0.43
  * 跳躍：拋物線，最高點 ≈ 0.75 m（特戰實測）
  * 反切 (Counter-Strafe)：朝移動反方向輸入時使用更強減速，
    使「急停」時間 ≈ 120ms（對比僅靠摩擦 ≈ 220ms）→ 射擊節奏的關鍵手感
  * 落地後 0.225s 內射擊準度懲罰 +7°（見 accuracy.py）

tick 順序（固定，保證確定性；所有伺服器 tick 皆依此順序執行）：
  1. 更新計時器：跳躍緩衝 (jump buffer)、土狼時間 (coyote time)
  2. 讀取姿態（下蹲/靜步）並計算當幀最大速度
  3. 水平移動（地面：加速/摩擦/反切；空中：輕微轉向）
  4. 施加重力（僅空中）
  5. 執行跳躍（在地面且緩衝有效時）
  6. 位置積分（顯式歐拉：pos += vel · dt）
  7. 地面夾取與落地偵測
"""

from __future__ import annotations

from dataclasses import dataclass

from server.core.math_core import EPSILON, Vec3, approach_vec, clamp


@dataclass(frozen=True, slots=True)
class MoveInput:
    """單 tick 的玩家「淨輸入」（伺服器收到的原始輸入，客戶端不可上送狀態）。"""

    forward: float = 0.0   # W(+1) / S(-1)
    strafe: float = 0.0    # D(+1) / A(-1)
    walk: bool = False     # Shift：靜步
    crouch: bool = False   # Ctrl：下蹲
    jump: bool = False     # 跳躍（邊緣觸發，由 jump buffer 吸收短暫延遲）
    ads: bool = False      # 開鏡（右鍵）：集彈 ×ads_spread_mult、移動 ×0.76


@dataclass(frozen=True, slots=True)
class MovementConfig:
    """移動模型參數。單位：m / s / m/s / m/s²。全部為可調參數。"""

    run_speed: float = 5.4          # 手持步槍跑速
    walk_ratio: float = 0.54        # 靜步 = 跑速 × 0.54（≈2.9 m/s，特戰實測）
    crouch_ratio: float = 0.43      # 下蹲 = 跑速 × 0.43
    jump_speed: float = 4.15        # 起跳初速（最高點 ≈ 0.75 m，特戰實測）
    gravity: float = 11.5           # 重力加速度（m/s²，向下）
    ground_accel: float = 22.0      # 地面加速 → 滿速約 245ms（特戰手感）
    ground_friction: float = 24.0   # 無輸入摩擦減速 → 滑停約 220ms
    opposite_decel: float = 45.0    # 反切減速 → 急停約 120ms（特戰 ~100-150ms）
    air_accel: float = 26.0         # 空中轉向加速（僅少量空中控制）
    air_speed_ratio: float = 1.0    # 空中最大水平速度倍率
    jump_buffer_time: float = 0.10  # 跳躍緩衝：落地前 0.1s 內按跳仍會跳
    jump_coyote_time: float = 0.10  # 土狼時間：離開平台後 0.1s 內仍可跳


class MovementController:
    """單一玩家角色的移動模擬。伺服器每個 tick 呼叫一次 step()。"""

    def __init__(self, cfg: MovementConfig | None = None, ground_y: float = 0.0):
        self.cfg = cfg if cfg is not None else MovementConfig()
        self.pos = Vec3(0.0, ground_y, 0.0)
        self.vel = Vec3()
        self.on_ground = True
        self.crouching = False
        self.walking = False
        self.ads = False
        self._ground_y = ground_y
        self.time_since_land = 999.0   # 距離上次落地經過的時間（落地準度懲罰用）
        self._jump_buffer = 0.0
        self._coyote = 0.0

    # ------------------------------------------------------------------ #
    # 查詢介面（供射擊/準度引擎與快照使用）
    # ------------------------------------------------------------------ #
    def current_max_speed(self) -> float:
        """依當前姿態回傳最大水平速度。"""
        run = self.cfg.run_speed
        if self.crouching:
            run *= self.cfg.crouch_ratio
        elif self.walking:
            run *= self.cfg.walk_ratio
        if self.ads:
            run *= 0.76          # 開鏡減速（特戰式）
        return run

    def horizontal_speed(self) -> float:
        return self.vel.horizontal().length()

    def speed_ratio(self) -> float:
        """0..1：目前水平速度佔跑速的比例（供 MovementErrorEngine 使用）。"""
        return clamp(self.horizontal_speed() / self.cfg.run_speed, 0.0, 1.0)

    # ------------------------------------------------------------------ #
    # 主迴圈：每 tick 呼叫
    # ------------------------------------------------------------------ #
    def step(self, inp: MoveInput, dt: float, speed_mult: float = 1.0) -> None:
        """每 tick 呼叫。

        :param speed_mult: 外部速度倍率（暈眩減速/刺激加速），作用於最大速度。
        """
        # 1) 計時器：跳躍緩衝 / 土狼時間
        self._jump_buffer = max(0.0, self._jump_buffer - dt)
        self._coyote = max(0.0, self._coyote - dt)
        if inp.jump:
            self._jump_buffer = self.cfg.jump_buffer_time

        # 2) 姿態
        self.crouching = inp.crouch
        self.walking = inp.walk
        self.ads = getattr(inp, "ads", False)

        # 3) 水平移動
        move_dir = Vec3(inp.strafe, 0.0, inp.forward)
        if move_dir.length_sq() > EPSILON:
            move_dir = move_dir.normalized()   # 斜向輸入對角線校正，避免超速
        if self.on_ground:
            self._coyote = self.cfg.jump_coyote_time
            self._ground_move(move_dir, dt, speed_mult)
        else:
            self._air_move(move_dir, dt, speed_mult)

        # 4) 重力（僅空中）
        if not self.on_ground:
            self.vel = Vec3(self.vel.x, self.vel.y - self.cfg.gravity * dt, self.vel.z)

        # 5) 跳躍：在地面且緩衝有效 → 執行（含土狼時間，見 _ground_move 中刷新）
        if self.on_ground and self._jump_buffer > 0.0:
            self.vel = Vec3(self.vel.x, self.cfg.jump_speed, self.vel.z)
            self.on_ground = False
            self._jump_buffer = 0.0

        # 6) 位置積分（顯式歐拉）
        self.pos = self.pos + self.vel * dt

        # 7) 地面夾取與落地偵測
        #    注意：落地後 pos.y == ground_y 且 vel.y == 0 仍會滿足本條件，
        #    因此僅在「空中→地面」轉換當 tick 重置 time_since_land，
        #    其餘 tick 一律累加計時，確保落地懲罰能正常衰減。
        was_airborne = not self.on_ground
        if self.pos.y <= self._ground_y and self.vel.y <= 0.0:
            if was_airborne:
                self.time_since_land = 0.0   # 剛落地：懲罰計時從 0 開始
            else:
                self.time_since_land += dt   # 穩定在地面：持續計時 → 懲罰正常衰減
            self.pos = Vec3(self.pos.x, self._ground_y, self.pos.z)
            self.vel = Vec3(self.vel.x, 0.0, self.vel.z)
            self.on_ground = True
        else:
            self.time_since_land += dt       # 空中：持續計時

    # ------------------------------------------------------------------ #
    # 內部：地面 / 空中水平移動
    # ------------------------------------------------------------------ #
    def _ground_move(self, move_dir: Vec3, dt: float, speed_mult: float = 1.0) -> None:
        max_speed = self.current_max_speed() * speed_mult
        hvel = self.vel.horizontal()
        if move_dir.length_sq() > EPSILON:
            # 反切偵測：目前速度與輸入方向夾角 > ~107° 時使用更強減速（急停）
            if hvel.length_sq() > EPSILON and hvel.normalized().dot(move_dir) < -0.3:
                decel = self.cfg.opposite_decel
            else:
                decel = self.cfg.ground_accel
            new_h = approach_vec(hvel, move_dir * max_speed, decel * dt)
        else:
            # 無輸入：靠摩擦減速（比反切慢）
            new_h = approach_vec(hvel, Vec3(), self.cfg.ground_friction * dt)

        # 地面水平速度上限 = 當幀最大速度（防止反切過程超速）
        if new_h.length_sq() > max_speed * max_speed:
            new_h = new_h.normalized() * max_speed
        self.vel = Vec3(new_h.x, self.vel.y, new_h.z)

    def _air_move(self, move_dir: Vec3, dt: float, speed_mult: float = 1.0) -> None:
        """空中僅能「輕微」轉向：保留跳躍拋物線，同時允許小幅空中修正。"""
        max_speed = self.cfg.run_speed * self.cfg.air_speed_ratio * speed_mult
        hvel = self.vel.horizontal()
        new_h = approach_vec(hvel, move_dir * max_speed, self.cfg.air_accel * dt)
        self.vel = Vec3(new_h.x, self.vel.y, new_h.z)
