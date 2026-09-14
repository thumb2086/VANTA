"""
server/netcode/client_loop.py — 客戶端迴圈（M2 + M3 預測/和解）
==============================================================
M2：淨輸入上送、快照接收、RTT 估算（EWMA）。
M3：客戶端預測 —— 本地以相同 MovementController 提前模擬；
    伺服器和解 —— 收到快照時若「預測位置 vs 伺服器位置」差異超過容差，
    回退到伺服器狀態並重放未確認輸入。
    Rollback 命中：射擊行動附帶「快照的 last_input_seq」→ 伺服器回滾命中。
"""

from __future__ import annotations

import math
from collections import deque

from server.core.math_core import Vec3
from server.core.movement import MovementConfig, MovementController, MoveInput
from server.netcode.protocol import (
    ACTION_SHOOT,
    ActionPacket,
    InputPacket,
    SnapshotPacket,
    WelcomePacket,
)
from server.netcode.timing import Clock

RECONCILE_TOLERANCE = 0.25   # 公尺：預測與伺服器差異超過此值才校正

# 客戶端預測牆壁碰撞（與 server/game/collision.py 同語義）
_PLAYER_RADIUS = 0.35
_PLAYER_HEIGHT = 1.8
_COLLISION_PASSES = 3


class GameClient:
    def __init__(
        self,
        transport,
        server_addr: object,
        clock: Clock,
        rtt_alpha: float = 0.25,
        move_cfg: MovementConfig | None = None,
        walls: list | None = None,
    ):
        self.transport = transport
        self.server_addr = server_addr
        self.clock = clock
        self.dt = 1.0 / 128.0

        self.out_seq = 0
        self.net_id: int | None = None
        self.slot: int | None = None

        # 客戶端預測用的地圖牆（(mn: Vec3, mx: Vec3) 列表；與伺服器一致）
        self.walls: list = walls or []

        self.rtt_ms: float = 0.0
        self.rtt_alpha = rtt_alpha
        self.last_snapshot: SnapshotPacket | None = None
        self.last_server_tick = -1
        self.snapshot_count = 0
        self.reconcile_count = 0

        # M3 客戶端預測
        self.local = MovementController(move_cfg)
        self.pending_inputs: deque[tuple[int, MoveInput]] = deque()
        self.predicted: dict[int, tuple] = {}          # seq -> (pos, vel, on_ground)

    # ------------------------------------------------------------------ #
    def poll(self) -> None:
        for src, data in self.transport.recv_from():
            if len(data) < 2 or data[0] != 0x56:
                continue
            if data[1] == 0x03:      # WELCOME
                wp = WelcomePacket.decode(data)
                if wp is not None:
                    self.net_id = wp.net_id
                    self.slot = wp.slot
                continue
            if data[1] == 0x02:      # SNAPSHOT
                snap = SnapshotPacket.decode(data)
                if snap is not None:
                    self._on_snapshot(snap)

    def _on_snapshot(self, snap: SnapshotPacket) -> None:
        self.last_snapshot = snap
        self.snapshot_count += 1
        if snap.server_tick > self.last_server_tick:
            self.last_server_tick = snap.server_tick
        if self.slot is not None:
            echo = snap.echo_for_slot(self.slot)
            if echo > 0:
                sample = self.clock.now() * 1000.0 - echo
                if sample >= 0.0:
                    if self.rtt_ms <= 0.0:
                        self.rtt_ms = sample
                    else:
                        self.rtt_ms = (1 - self.rtt_alpha) * self.rtt_ms + self.rtt_alpha * sample
            # M3 伺服器和解
            e = snap.state_for_slot(self.slot)
            if e is not None and e.occupied:
                self._reconcile(e)

    def _reconcile(self, e) -> None:
        last_seq = e.last_input_seq
        if last_seq in self.predicted:
            pp = self.predicted[last_seq][0]
            if pp.distance_to(e.pos) > RECONCILE_TOLERANCE:
                # 回退到伺服器狀態，重放未確認輸入
                self.local.pos = e.pos
                self.local.vel = e.vel
                self.local.on_ground = e.on_ground
                for seq, move in self.pending_inputs:
                    if seq > last_seq:
                        self.local.step(move, self.dt)
                        self._collide_local()
                self.reconcile_count += 1
        # 清理已確認的輸入
        self.pending_inputs = deque(x for x in self.pending_inputs if x[0] > last_seq)
        self.predicted = {s: v for s, v in self.predicted.items() if s > last_seq}

    def _collide_local(self) -> None:
        """預測牆壁碰撞（圓柱推離 + 消速度；與伺服器 collision.py 對齊）。"""
        if not self.walls:
            return
        p = self.local
        for _ in range(_COLLISION_PASSES):
            moved = False
            for mn, mx in self.walls:
                if p.pos.y + _PLAYER_HEIGHT <= mn.y or p.pos.y >= mx.y:
                    continue
                cx = min(max(p.pos.x, mn.x), mx.x)
                cz = min(max(p.pos.z, mn.z), mx.z)
                dx, dz = p.pos.x - cx, p.pos.z - cz
                d2 = dx * dx + dz * dz
                if d2 >= _PLAYER_RADIUS * _PLAYER_RADIUS - 1e-12:
                    continue
                if d2 > 1e-12:
                    d = math.sqrt(d2)
                    push = _PLAYER_RADIUS - d
                    nx, nz = dx / d, dz / d
                else:
                    cands = [
                        ((mn.x - _PLAYER_RADIUS) - p.pos.x, -1.0, 0.0),
                        ((mx.x + _PLAYER_RADIUS) - p.pos.x, 1.0, 0.0),
                        ((mn.z - _PLAYER_RADIUS) - p.pos.z, 0.0, -1.0),
                        ((mx.z + _PLAYER_RADIUS) - p.pos.z, 0.0, 1.0),
                    ]
                    best = min(cands, key=lambda c: abs(c[0]))
                    push, nx, nz = abs(best[0]), best[1], best[2]
                p.pos = Vec3(p.pos.x + nx * push, p.pos.y, p.pos.z + nz * push)
                vn = p.vel.x * nx + p.vel.z * nz
                if vn < 0.0:
                    p.vel = Vec3(p.vel.x - vn * nx, p.vel.y, p.vel.z - vn * nz)
                moved = True
            if not moved:
                break

    # ------------------------------------------------------------------ #
    def send_input(self, move: MoveInput) -> None:
        seq = self.out_seq
        # 客戶端預測：本地先行模擬
        self.local.step(move, self.dt)
        self._collide_local()
        self.predicted[seq] = (self.local.pos, self.local.vel, self.local.on_ground)
        self.pending_inputs.append((seq, move))
        if len(self.predicted) > 512:
            drop = sorted(self.predicted)[:64]
            for s in drop:
                del self.predicted[s]
            self.pending_inputs = deque(x for x in self.pending_inputs if x[0] > drop[-1])

        pkt = InputPacket(
            net_id=self.net_id if self.net_id is not None else 0,
            input_seq=seq,
            client_time_ms=int(round(self.clock.now() * 1000.0)),
            move=move,
        )
        self.transport.send_to(pkt.encode(), self.server_addr)
        self.out_seq += 1

    def send_action(self, action_id: int, p0: int = 0, p1: int = 0, p2: int = 0,
                    input_seq: int | None = None) -> None:
        """發送行動。射擊時 input_seq 應為「所見快照的 last_input_seq」（Rollback）。"""
        if input_seq is None:
            input_seq = self.out_seq
        pkt = ActionPacket(
            net_id=self.net_id if self.net_id is not None else 0,
            client_time_ms=int(round(self.clock.now() * 1000.0)),
            input_seq=input_seq,
            action_id=action_id,
            p0=p0,
            p1=p1,
            p2=p2,
        )
        self.transport.send_to(pkt.encode(), self.server_addr)

    def send_shot(self, yaw_deg: float, pitch_deg: float, input_seq: int | None = None) -> None:
        """對準 (yaw,pitch) 開火，附帶 Rollback 用 input_seq。"""
        self.send_action(ACTION_SHOOT, int(round(yaw_deg * 100)), int(round(pitch_deg * 100)), 0, input_seq)

    def snapshot_echo_seq(self) -> int | None:
        """目前所見快照中、屬於自己槽位的 last_input_seq（Rollback 基準）。"""
        if self.last_snapshot is not None and self.slot is not None:
            e = self.last_snapshot.state_for_slot(self.slot)
            if e is not None:
                return e.last_input_seq
        return None
