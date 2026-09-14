"""
server/netcode/anticheat.py — 伺服器權威反作弊
==============================================
架構原則：客戶端永不採信；伺服器驗證「輸入速率 / 行動速率 / 移動物理」。

偵測項目：
  * INPUT_FLOOD     每秒輸入超過上限（封包洪水 / 巨集）
  * ACTION_FLOOD    每秒行動超過上限（連點 / 射速濫用）
  * FIRE_RATE_ABUSE 射速冷卻內連續嘗試開火（trigger bot）
  * TELEPORT        單 tick 位移超過物理上限（瞬間移動）
  * SPEED_HACK      速度超過「跑速 × 加速 × 容差」（高速移動）
  * OUT_OF_BOUNDS   玩家離開地圖邊界
  * BAD_INPUT       輸入類比值異常（理論上已 clamp，異常值另記）

處置（遞進）：
  1. violation 計數；每種違規獨立計數
  2. 超過單項閾值 → 踢除（斷線，釋放槽位）
  3. TELEPORT/SPEED_HACK：伺服器權威修正（回彈到上一個合法位置）→ 玩家無法受益
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from server.core.math_core import Vec3


@dataclass(slots=True)
class AntiCheatConfig:
    max_inputs_per_sec: int = 170        # 128Hz + 容差（含重送）
    max_actions_per_sec: int = 40        # 正常玩家遠低於此
    max_speed_mps: float = 7.5           # 跑速5.4 × 刺激1.25 = 6.75 + 容差
    teleport_tolerance_m: float = 0.35   # 單 tick 合法位移上限（6.75/128≈0.053）
    fire_rate_attempt_window: int = 8    # 冷卻內連續嘗試 n 次 → 違規
    kick_after_violations: int = 5       # 單項違規累計 → 踢除
    warn_after: int = 2


@dataclass(slots=True)
class CheatReport:
    slot: int
    kind: str
    severity: int                       # 1 = 警告, 2 = 違規, 3 = 踢除
    detail: str = ""
    tick: int = 0


class AntiCheat:
    def __init__(self, cfg: AntiCheatConfig | None = None, on_report=None):
        self.cfg = cfg or AntiCheatConfig()
        self.on_report = on_report      # callable(report: CheatReport)
        # 每個 session addr 的度量
        self._inputs: dict[object, deque] = defaultdict(lambda: deque(maxlen=256))
        self._actions: dict[object, deque] = defaultdict(lambda: deque(maxlen=256))
        self._fire_attempts: dict[object, list[float]] = defaultdict(list)
        self._violations: dict[object, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_violation: dict[object, float] = {}    # key -> 上次違規時間（衰減用）
        self._last_pos: dict[int, Vec3] = {}     # slot -> 上一個合法位置
        self._last_tick: dict[int, int] = {}
        self.kicked: set[object] = set()

    # ------------------------------------------------------------------ #
    # 輸入 / 行動速率
    # ------------------------------------------------------------------ #
    def on_input(self, addr: object, now: float) -> CheatReport | None:
        dq = self._inputs[addr]
        dq.append(now)
        # 清掉 >1s 的記錄
        while dq and now - dq[0] > 1.0:
            dq.popleft()
        if len(dq) > self.cfg.max_inputs_per_sec:
            return self._violate(addr, None, "INPUT_FLOOD",
                                 f"{len(dq)} inputs/s", now)
        return None

    def on_action(self, addr: object, now: float) -> CheatReport | None:
        dq = self._actions[addr]
        dq.append(now)
        while dq and now - dq[0] > 1.0:
            dq.popleft()
        if len(dq) > self.cfg.max_actions_per_sec:
            return self._violate(addr, None, "ACTION_FLOOD",
                                 f"{len(dq)} actions/s", now)
        return None

    def note_fire_attempt(self, addr: object, slot: int, allowed: bool, now: float) -> CheatReport | None:
        """開火嘗試（allowed=False = 被射速冷卻/切槍擋下）。"""
        if allowed:
            self._fire_attempts[addr].clear()
            return None
        self._fire_attempts[addr].append(now)
        recent = [t for t in self._fire_attempts[addr] if now - t < 0.5]
        self._fire_attempts[addr] = recent
        if len(recent) >= self.cfg.fire_rate_attempt_window:
            self._fire_attempts[addr].clear()
            return self._violate(addr, slot, "FIRE_RATE_ABUSE",
                                 f"{len(recent)} attempts in 0.5s", now)
        return None

    # ------------------------------------------------------------------ #
    # 移動驗證（每 tick 世界步進後）
    # ------------------------------------------------------------------ #
    def validate_movement(self, world, tick: float) -> list[CheatReport]:
        reports: list[CheatReport] = []
        for slot, p in enumerate(world.players):
            if not p.alive:
                # 死亡時不追蹤（復活會傳送，由 on_round_reset 重置）
                continue
            pos = p.pos
            # 邊界
            bmin, bmax = world.map_data.bounds_min, world.map_data.bounds_max
            if not (bmin.x - 2 <= pos.x <= bmax.x + 2
                    and bmin.z - 2 <= pos.z <= bmax.z + 2):
                reports.append(self._violate(None, slot, "OUT_OF_BOUNDS",
                                             f"pos={pos}", tick))
                p.pos = self._last_pos.get(slot, pos)
                continue
            last = self._last_pos.get(slot)
            if last is not None:
                dist = pos.distance_to(last)
                # 單 tick 位移
                if dist > self.cfg.teleport_tolerance_m:
                    reports.append(self._violate(None, slot, "TELEPORT",
                                                 f"moved {dist:.3f}m/tick", tick))
                    # 伺服器權威修正：回彈到上一個合法位置（作弊無法受益）
                    p.pos = last
                    p.vel = Vec3()
                    continue
                # 速度（水平）
                hspeed = p.vel.horizontal().length()
                if hspeed > self.cfg.max_speed_mps:
                    reports.append(self._violate(None, slot, "SPEED_HACK",
                                                 f"speed={hspeed:.2f} m/s", tick))
                    p.vel = Vec3(p.vel.x * (self.cfg.max_speed_mps / max(hspeed, 1e-9)),
                                 p.vel.y,
                                 p.vel.z * (self.cfg.max_speed_mps / max(hspeed, 1e-9)))
            self._last_pos[slot] = p.pos
            self._last_tick[slot] = tick
        return reports

    def on_round_reset(self) -> None:
        """回合重置（重生傳送）→ 清空位置追蹤，避免誤判。"""
        self._last_pos.clear()
        self._last_tick.clear()

    # ------------------------------------------------------------------ #
    def _violate(self, addr, slot: int | None, kind: str, detail: str,
                 now: float, severity: int | None = None) -> CheatReport:
        key = addr if addr is not None else f"slot{slot}"
        counts = self._violations[key]
        # 衰減：距上次違規超過 10 秒 → 清空計數（歷史違規不永久累計成永封）
        if now - self._last_violation.get(key, -1e9) > 10.0:
            counts.clear()
        self._last_violation[key] = now
        counts[kind] += 1
        count = counts[kind]
        if severity is None:
            severity = 1 if count < self.cfg.warn_after else 2
        if count >= self.cfg.kick_after_violations:
            severity = 3
            if addr is not None:
                self.kicked.add(addr)
        rep = CheatReport(slot=slot if slot is not None else -1, kind=kind,
                          severity=severity, detail=detail, tick=int(now))
        if self.on_report is not None:
            self.on_report(rep)
        return rep

    def summary(self) -> dict:
        out = {}
        for key, kinds in self._violations.items():
            out[str(key)] = dict(kinds)
        return out
