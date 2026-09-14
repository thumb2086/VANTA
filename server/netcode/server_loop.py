"""
server/netcode/server_loop.py — 權威伺服器主迴圈（M2 + M3 + M4+ 行動）
=====================================================================
M2：收封包、Session、去重、緩衝、每 tick 每玩家 1 輸入、快照、斷線逾時。
M3：位置歷史（Ring Buffer）＋ seq→tick 對應 → Rollback 延遲補償命中。
M4+：行動封包（射擊/換彈/購買/Spike/技能）以固定順序處理，伺服器權威執行。

確定性：行動依「Session 加入序 × 行動 FIFO」處理；輸入依「槽位 × seq」處理。
回放：ingest_log 錄製所有入站封包 → 可無損重放。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.netcode.protocol import (
    ACTION_ABILITY,
    ACTION_BUY,
    ACTION_DEFUSE,
    ACTION_PLANT,
    ACTION_RELOAD,
    ACTION_SHOOT,
    ACTION_SWITCH,
    ACTION_INTERACT,
    EV_KILL,
    EV_MATCH_END,
    EV_ROUND_LOSS,
    EV_ROUND_WIN,
    EV_SPIKE_DEFUSED,
    EV_SPIKE_DETONATED,
    EV_SPIKE_PLANTED,
    MATCH_STATE_PACKET_SIZE,
    MAX_SLOTS,
    PHASE_ACTION,
    PHASE_BUY,
    PHASE_END,
    PHASE_FINISHED,
    SPIKE_DEFUSED,
    SPIKE_DETONATED,
    SPIKE_DEFUSING,
    SPIKE_IDLE,
    SPIKE_PLANTED,
    SPIKE_PLANTING,
    AbilityStatePacket,
    ActionPacket,
    GameEventPacket,
    InputPacket,
    MatchStatePacket,
    SnapshotEntry,
    SnapshotPacket,
    WelcomePacket,
    WorldStatePacket,
    weapon_item_id,
)
from server.netcode.anticheat import AntiCheat, AntiCheatConfig
from server.netcode.timing import Clock

HISTORY_CAPACITY = 256          # 1 秒 (128Hz) ×2 的補償視窗
MAX_ACTIONS_PER_TICK = 8
MATCH_STATE_INTERVAL = 128       # 每 128 ticks (1 秒) 廣播一次 MatchState
SNAPSHOT_INTERVAL = 8            # 每 8 ticks (16Hz) 廣播快照——128Hz 全量廣播
                                 # 會洪泛 WebSocket（RTT 爆衝到秒級），16Hz
                                 # 搭配客戶端插值已足夠平滑（特戰同款思路）


@dataclass(slots=True)
class PlayerSession:
    net_id: int
    slot: int
    addr: object
    created_at: float
    last_activity: float
    pending: list[InputPacket] = field(default_factory=list)
    pending_actions: list[ActionPacket] = field(default_factory=list)
    seq_ticks: dict[int, int] = field(default_factory=dict)   # input_seq -> 伺服器 tick
    last_processed_seq: int = -1
    echo_client_time_ms: int = 0
    seen: set[int] = field(default_factory=set)
    last_move: MoveInput = field(default_factory=MoveInput)   # 無新輸入時沿用（128Hz > 送率）

    def prune_seen(self, window: int = 128) -> None:
        if len(self.seen) > window * 2:
            hi = max(self.seen)
            self.seen = {s for s in self.seen if s > hi - window}

    def prune_seq_ticks(self, window: int = HISTORY_CAPACITY * 2) -> None:
        if len(self.seq_ticks) > window:
            drop = sorted(self.seq_ticks)[: window // 4]
            for s in drop:
                del self.seq_ticks[s]


class GameServer:
    def __init__(
        self,
        world: World,
        transport,
        clock: Clock,
        rate_hz: int = 128,
        timeout_s: float = 8.0,
    ):
        self.world = world
        self.transport = transport
        self.clock = clock
        self.rate_hz = rate_hz
        self.dt = 1.0 / rate_hz
        self.timeout_s = timeout_s

        self.sessions: dict[object, PlayerSession] = {}
        self.free_slots: list[int] = list(range(MAX_SLOTS))
        self.tick = 0
        self._next_net_id = 1
        self.pos_history: deque[tuple[int, list[Vec3]]] = deque(maxlen=HISTORY_CAPACITY)

        self.on_player_joined: Callable[[PlayerSession], None] | None = None
        self.on_player_left: Callable[[PlayerSession], None] | None = None
        self.on_cheat_report: Callable | None = None     # 外部監聽（記分/日誌）
        self.ingest_log: list[tuple[int, object, bytes]] = []

        # 反作弊（伺服器權威）
        self.anticheat = AntiCheat(AntiCheatConfig())
        self._slot_addrs: dict[int, object] = {}
        self._last_match_round = 0

        # 遊戲事件發送（diff 偵測，伺服器權威）
        self._prev_log_len = 0
        self._prev_spike_state: str | None = None
        self._prev_phase: str | None = None
        self._prev_scores: tuple[int, int] = (0, 0)
        self.events_sent = 0

        # AI/觀戰模式：快照包含全部 10 名玩家（不論有無 session）
        self.broadcast_all_slots: bool = False

    # ------------------------------------------------------------------ #
    def step(self, dt: float | None = None, ai_inputs: dict[int, MoveInput] | None = None) -> None:
        """推進一個 tick。

        :param ai_inputs: 額外的「無 Session 槽位」輸入（如伺服器內建 AI 機器人），
                          僅在該槽位沒有真人 Session 時使用；真人輸入優先。
        """
        dt = dt if dt is not None else self.dt
        self._handle_incoming()
        self._sweep_timeouts()
        self._process_actions()

        inputs: list[MoveInput | None] = [None] * MAX_SLOTS
        for addr, sess in self.sessions.items():
            move = self._take_next_input(sess)
            # 128Hz tick > 客戶端送率：無新輸入時「沿用上一筆」而非歸零，
            # 否則速度每秒被摩擦煞車數十次 → 半速抖動（與客戶端預測持續分歧）。
            if move is not None:
                sess.last_move = move
            inputs[sess.slot] = sess.last_move
        if ai_inputs:
            for slot, move in ai_inputs.items():
                if 0 <= slot < MAX_SLOTS and inputs[slot] is None:
                    inputs[slot] = move

        self.world.step(inputs, dt)
        self.tick += 1
        self.pos_history.append((self.tick, [p.pos for p in self.world.players]))

        # 反作弊：移動驗證（瞬間移動 / 高速 / 出界 → 修正或踢除）
        for rep in self.anticheat.validate_movement(self.world, self.tick):
            self._handle_cheat(None, rep)
        # 回合切換（重生傳送）→ 重置位置追蹤避免誤判
        match = getattr(self.world, "match", None)
        if match is not None and match.round != self._last_match_round:
            self.anticheat.on_round_reset()
            self._last_match_round = match.round

        self._emit_game_events()
        if self.tick % SNAPSHOT_INTERVAL == 0:
            self._broadcast_snapshot()
            self._broadcast_world_state()
        # 定期廣播 MatchState（比分/回合/階段/Spike/經濟）+ 技能冷卻
        if self.tick % MATCH_STATE_INTERVAL == 0:
            self._broadcast_match_state()
            self._broadcast_ability_state()

    # ------------------------------------------------------------------ #
    # 收包路徑
    # ------------------------------------------------------------------ #
    def _handle_incoming(self) -> None:
        if self.transport is None:
            return
        for src, data in self.transport.recv_from():
            self.ingest_log.append((self.tick, src, data))
            self._ingest(src, data)

    def ingest(self, addr: object, data: bytes) -> None:
        self.ingest_log.append((self.tick, addr, data))
        self._ingest(addr, data)

    def _ingest(self, addr: object, data: bytes) -> None:
        if len(data) < 2 or data[0] != 0x56:
            return
        if data[1] == 0x01:      # INPUT
            pkt = InputPacket.decode(data)
            if pkt is None:
                return
            sess = self._session_for(addr)
            if sess is None:
                return
            sess.last_activity = self.clock.now()
            # 反作弊：輸入速率
            rep = self.anticheat.on_input(addr, self.clock.now())
            self._handle_cheat(addr, rep)
            if pkt.input_seq <= sess.last_processed_seq or pkt.input_seq in sess.seen:
                return
            sess.seen.add(pkt.input_seq)
            sess.prune_seen()
            import bisect

            bisect.insort(sess.pending, pkt, key=lambda p: p.input_seq)
        elif data[1] == 0x04:    # ACTION
            pkt = ActionPacket.decode(data)
            if pkt is None:
                return
            sess = self._session_for(addr)
            if sess is None:
                return
            sess.last_activity = self.clock.now()
            # 反作弊：行動速率
            rep = self.anticheat.on_action(addr, self.clock.now())
            self._handle_cheat(addr, rep)
            sess.pending_actions.append(pkt)

    def _session_for(self, addr: object) -> PlayerSession | None:
        sess = self.sessions.get(addr)
        if sess is None:
            sess = self._create_session(addr)
        return sess

    def _create_session(self, addr: object) -> PlayerSession:
        slot = self.free_slots.pop(0)
        sess = PlayerSession(
            net_id=self._next_net_id,
            slot=slot,
            addr=addr,
            created_at=self.clock.now(),
            last_activity=self.clock.now(),
        )
        self._next_net_id += 1
        self.sessions[addr] = sess
        self._slot_addrs[sess.slot] = addr
        if self.transport is not None:
            self.transport.send_to(WelcomePacket(sess.net_id, sess.slot).encode(), addr)
        if self.on_player_joined is not None:
            self.on_player_joined(sess)
        return sess

    # ------------------------------------------------------------------ #
    # 行動處理（伺服器權威，固定順序）
    # ------------------------------------------------------------------ #
    def _process_actions(self) -> None:
        # 複製清單：_apply_action 可能因反作弊踢除而修改 self.sessions
        for sess in list(self.sessions.values()):
            for _ in range(MAX_ACTIONS_PER_TICK):
                if not sess.pending_actions:
                    break
                act = sess.pending_actions.pop(0)
                self._apply_action(sess, act)

    def _apply_action(self, sess: PlayerSession, act: ActionPacket) -> None:
        w = self.world
        p = w.players[sess.slot]
        if act.action_id == ACTION_SHOOT:
            if p.alive and w.match is None or (w.match is not None and w.match.phase.value == "action"):
                # 反作弊：射速濫用偵測（冷卻內連續嘗試）
                allowed = (p.alive and not p.inventory.switching(w.time)
                           and p.weapon.can_fire(w.time))
                rep = self.anticheat.note_fire_attempt(sess.addr, sess.slot, allowed, self.clock.now())
                self._handle_cheat(sess.addr, rep)
                if not allowed:
                    return
                yaw = act.p0 / 100.0
                pitch = act.p1 / 100.0
                target_positions = self._positions_at(act.input_seq)
                w.fire_shot(sess.slot, yaw, pitch, target_positions)
        elif act.action_id == ACTION_RELOAD:
            p.weapon.start_reload(w.time)
        elif act.action_id == ACTION_SWITCH:
            p.switch_weapon(act.p0)
        elif act.action_id == ACTION_INTERACT:
            # F 鍵地圖互動（繩索/鐵門）
            w.interact(sess.slot)
        elif act.action_id == ACTION_BUY:
            item = act.p0
            if item >= 9000:
                p.buy_shield(item - 8999)
            else:
                key = weapon_item_id(item)
                if key is not None:
                    p.buy_weapon(key)
        elif act.action_id == ACTION_PLANT:
            if w.spike is not None:
                w.spike.set_hold_plant(sess.slot, bool(act.p0))
        elif act.action_id == ACTION_DEFUSE:
            if w.spike is not None:
                w.spike.set_hold_defuse(sess.slot, bool(act.p0))
        elif act.action_id == ACTION_ABILITY:
            idx = act.p0
            yaw = act.p1 / 100.0
            pitch = act.p2 / 100.0
            w.cast_ability(sess.slot, idx, yaw, pitch)

    def _positions_at(self, input_seq: int) -> dict[int, Vec3] | None:
        """Rollback：找出 input_seq 對應 tick 的玩家位置（補償視窗內）。"""
        sess = None
        for s in self.sessions.values():
            if input_seq in s.seq_ticks:
                sess = s
                break
        if sess is None:
            return None
        target_tick = sess.seq_ticks[input_seq]
        for tick, positions in self.pos_history:
            if tick == target_tick:
                return {i: positions[i] for i in range(len(positions))}
        # 不在視窗內（過舊/過新）→ 退回目前位置（不補償）
        return None

    # ------------------------------------------------------------------ #
    # 輸入消費
    # ------------------------------------------------------------------ #
    def _take_next_input(self, sess: PlayerSession) -> MoveInput | None:
        while sess.pending:
            pkt = sess.pending[0]
            if pkt.input_seq <= sess.last_processed_seq:
                sess.pending.pop(0)
                continue
            sess.pending.pop(0)
            sess.last_processed_seq = pkt.input_seq
            sess.echo_client_time_ms = pkt.client_time_ms
            # seq -> tick：記錄「本步結束時的 tick」，與快照 tick 對齊
            sess.seq_ticks[pkt.input_seq] = self.tick + 1
            sess.prune_seq_ticks()
            return pkt.move
        return None

    # ------------------------------------------------------------------ #
    def _sweep_timeouts(self) -> None:
        now = self.clock.now()
        dead = [addr for addr, s in self.sessions.items() if now - s.last_activity > self.timeout_s]
        for addr in dead:
            self._remove_session(addr)

    def _remove_session(self, addr: object) -> None:
        """移除 Session（斷線逾時 / 反作弊踢除共用），釋放槽位。"""
        sess = self.sessions.pop(addr, None)
        if sess is None:
            return
        self._slot_addrs.pop(sess.slot, None)
        self.free_slots.append(sess.slot)
        self.free_slots.sort()
        if self.on_player_left is not None:
            self.on_player_left(sess)

    def _handle_cheat(self, addr, rep) -> None:
        """反作弊處置：回報外部 → severity 3 踢除。"""
        if rep is None:
            return
        if self.on_cheat_report is not None:
            self.on_cheat_report(rep)
        if rep.severity >= 3:
            target = addr if addr is not None else self._slot_addrs.get(rep.slot)
            if target is not None and target in self.sessions:
                self.world.event_log.append(
                    f"KICK: slot{rep.slot} ({rep.kind}: {rep.detail})")
                self._remove_session(target)

    def _broadcast_snapshot(self) -> None:
        if self.transport is None:
            return
        entries: list[SnapshotEntry] = []

        if self.broadcast_all_slots:
            # AI/觀戰模式：廣播全部活著的玩家（含無 session 的 AI 機器人）
            slot_sess: dict[int, PlayerSession] = {s.slot: s for s in self.sessions.values()}
            for slot, st in enumerate(self.world.players):
                if not st.alive:
                    continue
                sess = slot_sess.get(slot)
                entries.append(
                    SnapshotEntry(
                        slot=slot,
                        pos=st.pos,
                        vel=st.vel,
                        on_ground=st.on_ground,
                        crouching=st.crouching,
                        walking=st.walking,
                        occupied=True,
                        echo_client_time_ms=sess.echo_client_time_ms if sess else 0,
                        last_input_seq=sess.last_processed_seq if sess else -1,
                        health=int(round(st.health)),
                        mag=st.weapon.mag,
                        reloading=st.weapon.reloading,
                        weapon_slot=st.inventory.active,
                        reload_progress=_reload_progress_byte(st),
                    )
                )
        else:
            for addr, sess in self.sessions.items():
                st = self.world.players[sess.slot]
                entries.append(
                    SnapshotEntry(
                        slot=sess.slot,
                        pos=st.pos,
                        vel=st.vel,
                        on_ground=st.on_ground,
                        crouching=st.crouching,
                        walking=st.walking,
                        occupied=True,
                        echo_client_time_ms=sess.echo_client_time_ms,
                        last_input_seq=sess.last_processed_seq,
                        health=int(round(st.health)),
                        mag=st.weapon.mag,
                        reloading=st.weapon.reloading,
                        weapon_slot=st.inventory.active,
                        reload_progress=_reload_progress_byte(st),
                    )
                )

        snap = SnapshotPacket(server_tick=self.tick, entries=entries)
        payload = snap.encode()
        for sess in self.sessions.values():
            self.transport.send_to(payload, sess.addr)

    # ------------------------------------------------------------------ #
    # 遊戲事件廣播（擊殺 / Spike / 回合，供客戶端表現層）
    # ------------------------------------------------------------------ #
    def _emit_game_events(self) -> None:
        if self.transport is None:
            return
        w = self.world
        # 1) 擊殺（比對 event_log）
        for entry in w.event_log[self._prev_log_len :]:
            # 格式: "kill: slotX by slotY (weapon)"
            if entry.startswith("kill: "):
                body = entry[len("kill: ") :]
                victim_s, rest = body.split(" by ", 1)
                killer_s = rest.split(" (", 1)[0]
                try:
                    victim = int(victim_s.replace("slot", ""))
                    killer = int(killer_s.replace("slot", ""))
                except ValueError:
                    continue
                self._broadcast_event(GameEventPacket(EV_KILL, self.tick, killer, victim))
        self._prev_log_len = len(w.event_log)

        # 2) Spike 狀態轉移
        spike = getattr(w, "spike", None)
        if spike is not None:
            st = spike.state.value
            if st != self._prev_spike_state and self._prev_spike_state is not None:
                mapping = {
                    "planted": EV_SPIKE_PLANTED,
                    "defused": EV_SPIKE_DEFUSED,
                    "detonated": EV_SPIKE_DETONATED,
                }
                if st in mapping:
                    self._broadcast_event(GameEventPacket(mapping[st], self.tick))
            self._prev_spike_state = st

        # 3) 回合勝負 / 比賽結束
        match = getattr(w, "match", None)
        if match is not None:
            scores = (match.scores[0], match.scores[1])
            if scores != self._prev_scores and self._prev_scores is not None:
                winner = 0 if scores[0] > self._prev_scores[0] else 1
                if match.phase.value == "finished":
                    self._broadcast_event(GameEventPacket(EV_MATCH_END, self.tick, winner))
                elif winner == 0:
                    self._broadcast_event(GameEventPacket(EV_ROUND_WIN, self.tick))
                else:
                    self._broadcast_event(GameEventPacket(EV_ROUND_LOSS, self.tick))
            self._prev_scores = scores

    def _broadcast_event(self, pkt: GameEventPacket) -> None:
        if self.transport is None:
            return
        payload = pkt.encode()
        for sess in self.sessions.values():
            self.transport.send_to(payload, sess.addr)
        self.events_sent += 1

    def _broadcast_match_state(self) -> None:
        """廣播 MatchState 封包（比分/回合/階段/Spike/經濟），每秒一次。"""
        if self.transport is None or not self.sessions:
            return
        w = self.world
        match = getattr(w, "match", None)
        if match is None:
            return
        # 階段映射
        phase_map = {
            "buy": PHASE_BUY, "action": PHASE_ACTION,
            "end": PHASE_END, "finished": PHASE_FINISHED,
        }
        phase = phase_map.get(match.phase.value, PHASE_BUY)
        round_timer_ms = int(max(0, match.phase_timer) * 1000)
        # Spike 狀態
        spike = getattr(w, "spike", None)
        spike_state = SPIKE_IDLE
        spike_fuse = 0
        if spike is not None:
            spike_map = {
                "idle": SPIKE_IDLE, "planting": SPIKE_PLANTING,
                "planted": SPIKE_PLANTED, "defusing": SPIKE_DEFUSING,
                "detonated": SPIKE_DETONATED, "defused": SPIKE_DEFUSED,
            }
            spike_state = spike_map.get(spike.state.value, SPIKE_IDLE)
            if spike_state == SPIKE_PLANTED:
                spike_fuse = int(max(0, spike.fuse))
        # 經濟
        credits = tuple(int(p.economy.credits) for p in w.players)
        pkt = MatchStatePacket(
            server_tick=self.tick,
            phase=phase,
            round=match.round,
            round_timer_ms=round_timer_ms,
            spike_state=spike_state,
            spike_fuse_s=spike_fuse,
            score_a=match.scores.get(0, 0),
            score_b=match.scores.get(1, 0),
            attacker_team=match.attackers(),
            credits=credits,
        )
        payload = pkt.encode()
        for sess in self.sessions.values():
            self.transport.send_to(payload, sess.addr)

    def _broadcast_ability_state(self) -> None:
        """廣播 AbilityState 封包（各玩家技能冷卻），每秒一次。"""
        if self.transport is None or not self.sessions:
            return
        w = self.world
        cooldowns = []
        for p in w.players:
            cds = p.abilities.snapshot()
            # 取每個技能的冷卻（最多 4 個）
            slot_cds = [0.0] * 4
            for i, s in enumerate(cds[:4]):
                slot_cds[i] = s.get("cooldown", 0.0)
            cooldowns.append(tuple(slot_cds))
        pkt = AbilityStatePacket(
            server_tick=self.tick,
            cooldowns=tuple(cooldowns),
        )
        payload = pkt.encode()
        for sess in self.sessions.values():
            self.transport.send_to(payload, sess.addr)

    def _broadcast_world_state(self) -> None:
        """廣播 WorldState 封包（煙霧位置/半徑/剩餘時間），與快照同頻。"""
        if self.transport is None or not self.sessions:
            return
        w = self.world
        smokes_data = []
        for s in w.smokes:
            if not s.active:
                continue
            c = s.center
            smokes_data.append((c.x, c.y, c.z, s.radius, s.time_left, 0))
        pkt = WorldStatePacket(server_tick=self.tick, smokes=tuple(smokes_data))
        payload = pkt.encode()
        for sess in self.sessions.values():
            self.transport.send_to(payload, sess.addr)


def _reload_progress_byte(st) -> int:
    """換彈進度 → u8：255=未換彈，0..254=進度。伺服器權威（驅動客戶端動畫/音效同步）。"""
    w = st.weapon
    if not w.reloading:
        return 255
    frac = min(1.0, w.reload_progress / max(1e-9, w.stats.reload_time))
    return int(max(0, min(254, frac * 254)))
