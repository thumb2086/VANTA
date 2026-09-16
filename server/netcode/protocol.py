"""
server/netcode/protocol.py — 二進位封包協定
===========================================
封包格式（little-endian，全部為定長，方便解析與 fuzz 防禦）：

  MAGIC = 0x56 ('V')

  0x01 INPUT   (15 B)：  net_id u16 | input_seq u32 | client_time_ms u32 |
                         forward i8 | strafe i8 | flags u8
  flags: bit0=walk bit1=crouch bit2=jump

  0x02 SNAPSHOT (190 B)： server_tick u32 | player_count u8 | reserved[3] |
                         per-slot (18 B × 10)： slot u8 | flags u8 |
                         pos xyz i16 (×0.01 m) | vel xyz i16 (×0.01 m/s) |
                         echo_client_time_ms u32
  flags: bit0=on_ground bit1=crouch bit2=walking bit3=occupied

  0x03 WELCOME (6 B)：   net_id u16 | slot u8 | reserved[3]

量化策略：
  * 位置：0.01 m (cm) 精度，int16 涵蓋 ±327.67 m（大於任何競技地圖）
  * 速度：0.01 m/s 精度，int16 涵蓋 ±327.67 m/s
  * 類比輸入：-1..1 → int8 (×127)

這是「線上格式」；伺服器內部模擬永遠使用 float64，位元級確定性不受影響。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from server.core.math_core import Vec3, clamp
from server.core.movement import MoveInput

MAGIC = 0x56
TYPE_INPUT = 0x01
TYPE_SNAPSHOT = 0x02
TYPE_WELCOME = 0x03
TYPE_ACTION = 0x04
TYPE_GAME_EVENT = 0x05
TYPE_MATCH_STATE = 0x06
TYPE_ABILITY_STATE = 0x07
TYPE_WORLD_STATE = 0x09    # 煙霧/閃光等世界物件狀態

# 玩家行動代碼（ACTION 封包）
ACTION_SHOOT = 0x01
ACTION_RELOAD = 0x02
ACTION_BUY = 0x03
ACTION_PLANT = 0x04
ACTION_DEFUSE = 0x05
ACTION_ABILITY = 0x06
ACTION_SWITCH = 0x07
ACTION_INTERACT = 0x08    # F 鍵地圖互動（繩索/鐵門）

# 遊戲事件代碼（GAME_EVENT 封包，客戶端表現層使用）
EV_KILL = 1
EV_SPIKE_PLANTED = 2
EV_SPIKE_DEFUSED = 3
EV_SPIKE_DETONATED = 4
EV_ROUND_WIN = 5
EV_ROUND_LOSS = 6
EV_MATCH_END = 7
EV_ASSIST = 8
EV_STREAK = 9      # p0=streak(2/3/4/5), p1=killer slot
EV_CLUTCH = 10     # p0=clutcher slot, p1=vs count
EV_ORB = 11        # p0=orb kind index, p1=capturer slot

MAX_SLOTS = 10

# 封包總長度（驗證/測試用）
INPUT_PACKET_SIZE = 15
ACTION_PACKET_SIZE = 19
GAME_EVENT_PACKET_SIZE = 16
MATCH_STATE_PACKET_SIZE = 36
ABILITY_STATE_ENTRY_SIZE = 8   # 每人 8 bytes（見 AbilityStatePacket 佈局）
ABILITY_STATE_PACKET_SIZE = 6 + MAX_SLOTS * ABILITY_STATE_ENTRY_SIZE
# 0x09 WORLD_STATE：header 6B + count u8 + reserved u8 + max 8 煙霧 × 14B = 6 + 2 + 112 = 120
WORLD_STATE_HEADER_SIZE = 8
WORLD_STATE_SMOKE_ENTRY_SIZE = 14
MAX_WORLD_SMOKES = 8
WORLD_STATE_PACKET_SIZE = WORLD_STATE_HEADER_SIZE + MAX_WORLD_SMOKES * WORLD_STATE_SMOKE_ENTRY_SIZE
WELCOME_PACKET_SIZE = 6
SNAPSHOT_HEADER_SIZE = 10
SNAPSHOT_ENTRY_SIZE = 26
SNAPSHOT_PACKET_SIZE = SNAPSHOT_HEADER_SIZE + MAX_SLOTS * SNAPSHOT_ENTRY_SIZE  # 270

# flag 位元
FLAG_WALK = 0x01
FLAG_ADS = 0x08
FLAG_CROUCH = 0x02
FLAG_JUMP = 0x04
FLAG_ON_GROUND = 0x01
FLAG_OCCUPIED = 0x08
FLAG_RELOADING = 0x10

_QUANT = 0.01          # 位置/速度量化步長 (m / m/s)
_I8_MAX = 127.0


def _q16(value: float) -> int:
    """float → int16 定點（0.01 解析度），夾取防溢出。"""
    return int(round(clamp(value, -327.67, 327.67) / _QUANT))


def _unq16(raw: int) -> float:
    """int16 定點 → float。"""
    return raw * _QUANT


def _i8(value: float) -> int:
    """-1..1 → int8。"""
    return int(round(clamp(value, -1.0, 1.0) * _I8_MAX))


def _uni8(raw: int) -> float:
    return raw / _I8_MAX


# ---------------------------------------------------------------------- #
# 0x01 INPUT
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class InputPacket:
    net_id: int
    input_seq: int
    client_time_ms: int
    move: MoveInput

    def encode(self) -> bytes:
        data = bytearray(INPUT_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_INPUT
        struct.pack_into("<H", data, 2, self.net_id & 0xFFFF)
        struct.pack_into("<I", data, 4, self.input_seq & 0xFFFFFFFF)
        struct.pack_into("<I", data, 8, self.client_time_ms & 0xFFFFFFFF)
        struct.pack_into("<b", data, 12, _i8(self.move.forward))
        struct.pack_into("<b", data, 13, _i8(self.move.strafe))
        flags = 0
        if self.move.walk:
            flags |= FLAG_WALK
        if self.move.crouch:
            flags |= FLAG_CROUCH
        if self.move.jump:
            flags |= FLAG_JUMP
        if getattr(self.move, "ads", False):
            flags |= FLAG_ADS
        data[14] = flags
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "InputPacket | None":
        if len(data) != INPUT_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_INPUT:
            return None
        net_id = struct.unpack_from("<H", data, 2)[0]
        input_seq = struct.unpack_from("<I", data, 4)[0]
        client_time_ms = struct.unpack_from("<I", data, 8)[0]
        forward = _uni8(struct.unpack_from("<b", data, 12)[0])
        strafe = _uni8(struct.unpack_from("<b", data, 13)[0])
        flags = data[14]
        return InputPacket(
            net_id=net_id,
            input_seq=input_seq,
            client_time_ms=client_time_ms,
            move=MoveInput(
                forward=forward,
                strafe=strafe,
                walk=bool(flags & FLAG_WALK),
                crouch=bool(flags & FLAG_CROUCH),
                jump=bool(flags & FLAG_JUMP),
                ads=bool(flags & FLAG_ADS),
            ),
        )


# ---------------------------------------------------------------------- #
# 0x02 SNAPSHOT
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    slot: int
    pos: Vec3
    vel: Vec3
    on_ground: bool
    crouching: bool
    walking: bool
    occupied: bool
    echo_client_time_ms: int
    last_input_seq: int = -1
    health: int = 100
    mag: int = 0
    reloading: bool = False
    weapon_slot: int = 0
    reload_progress: int = 255      # 0..254 = 換彈進度，255 = 未在換彈（伺服器權威）

    def _flags(self) -> int:
        f = 0
        if self.on_ground:
            f |= FLAG_ON_GROUND
        if self.crouching:
            f |= FLAG_CROUCH
        if self.walking:
            f |= FLAG_WALK
        if self.occupied:
            f |= FLAG_OCCUPIED
        if self.reloading:
            f |= FLAG_RELOADING
        return f

    @staticmethod
    def _from_flags(f: int) -> tuple[bool, bool, bool, bool, bool]:
        return (
            bool(f & FLAG_ON_GROUND),
            bool(f & FLAG_CROUCH),
            bool(f & FLAG_WALK),
            bool(f & FLAG_OCCUPIED),
            bool(f & FLAG_RELOADING),
        )


@dataclass(slots=True)
class SnapshotPacket:
    server_tick: int
    entries: list[SnapshotEntry] = field(default_factory=list)

    def state_for_slot(self, slot: int) -> SnapshotEntry | None:
        for e in self.entries:
            if e.slot == slot:
                return e
        return None

    def echo_for_slot(self, slot: int) -> int:
        e = self.state_for_slot(slot)
        return e.echo_client_time_ms if e is not None else 0

    def encode(self) -> bytes:
        data = bytearray(SNAPSHOT_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_SNAPSHOT
        struct.pack_into("<I", data, 2, self.server_tick & 0xFFFFFFFF)
        data[6] = len(self.entries)
        # 依 slot 填入（未提供的槽位保持 occupied=0）
        by_slot = {e.slot: e for e in self.entries}
        for slot in range(MAX_SLOTS):
            e = by_slot.get(slot)
            off = SNAPSHOT_HEADER_SIZE + slot * SNAPSHOT_ENTRY_SIZE
            if e is None:
                struct.pack_into("<B", data, off + 1, 0)  # flags=0 → 未佔用
                struct.pack_into("<I", data, off + 12, 0)
                struct.pack_into("<I", data, off + 18, 0)
                continue
            struct.pack_into("<B", data, off, e.slot & 0xFF)
            struct.pack_into("<B", data, off + 1, e._flags())
            struct.pack_into("<h", data, off + 2, _q16(e.pos.x))
            struct.pack_into("<h", data, off + 4, _q16(e.pos.y))
            struct.pack_into("<h", data, off + 6, _q16(e.pos.z))
            struct.pack_into("<h", data, off + 8, _q16(e.vel.x))
            struct.pack_into("<h", data, off + 10, _q16(e.vel.y))
            struct.pack_into("<h", data, off + 12, _q16(e.vel.z))
            struct.pack_into("<I", data, off + 14, e.echo_client_time_ms & 0xFFFFFFFF)
            struct.pack_into("<I", data, off + 18, e.last_input_seq & 0xFFFFFFFF)
            struct.pack_into("<B", data, off + 22, clamp(e.health, 0, 255) & 0xFF)
            struct.pack_into("<B", data, off + 23, clamp(e.mag, 0, 255) & 0xFF)
            struct.pack_into("<B", data, off + 24, clamp(e.weapon_slot, 0, 255) & 0xFF)
            struct.pack_into("<B", data, off + 25, clamp(e.reload_progress, 0, 255) & 0xFF)
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "SnapshotPacket | None":
        if len(data) != SNAPSHOT_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_SNAPSHOT:
            return None
        server_tick = struct.unpack_from("<I", data, 2)[0]
        count = data[6]
        entries: list[SnapshotEntry] = []
        for slot in range(MAX_SLOTS):
            off = SNAPSHOT_HEADER_SIZE + slot * SNAPSHOT_ENTRY_SIZE
            flags = data[off + 1]
            on_ground, crouching, walking, occupied, reloading = SnapshotEntry._from_flags(flags)
            if not occupied:
                continue
            px, py, pz = struct.unpack_from("<hhh", data, off + 2)
            vx, vy, vz = struct.unpack_from("<hhh", data, off + 8)
            echo = struct.unpack_from("<I", data, off + 14)[0]
            last_seq = struct.unpack_from("<I", data, off + 18)[0]
            health = data[off + 22]
            mag = data[off + 23]
            weapon_slot = data[off + 24]
            reload_progress = data[off + 25]
            entries.append(
                SnapshotEntry(
                    slot=slot,
                    pos=Vec3(_unq16(px), _unq16(py), _unq16(pz)),
                    vel=Vec3(_unq16(vx), _unq16(vy), _unq16(vz)),
                    on_ground=on_ground,
                    crouching=crouching,
                    walking=walking,
                    occupied=occupied,
                    echo_client_time_ms=echo,
                    last_input_seq=last_seq,
                    health=health,
                    mag=mag,
                    reloading=reloading,
                    weapon_slot=weapon_slot,
                    reload_progress=reload_progress,
                )
            )
        # count 僅供參考，實際以 slot 條目為準
        _ = count
        return SnapshotPacket(server_tick=server_tick, entries=entries)


# ---------------------------------------------------------------------- #
# 0x03 WELCOME
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class WelcomePacket:
    net_id: int
    slot: int

    def encode(self) -> bytes:
        data = bytearray(WELCOME_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_WELCOME
        struct.pack_into("<H", data, 2, self.net_id & 0xFFFF)
        data[4] = self.slot & 0xFF
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "WelcomePacket | None":
        if len(data) != WELCOME_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_WELCOME:
            return None
        net_id = struct.unpack_from("<H", data, 2)[0]
        slot = data[4]
        return WelcomePacket(net_id=net_id, slot=slot)


# ---------------------------------------------------------------------- #
# 0x04 ACTION
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ActionPacket:
    net_id: int
    client_time_ms: int
    input_seq: int
    action_id: int
    p0: int = 0
    p1: int = 0
    p2: int = 0

    def encode(self) -> bytes:
        data = bytearray(ACTION_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_ACTION
        struct.pack_into("<H", data, 2, self.net_id & 0xFFFF)
        struct.pack_into("<I", data, 4, self.client_time_ms & 0xFFFFFFFF)
        struct.pack_into("<I", data, 8, self.input_seq & 0xFFFFFFFF)
        data[12] = self.action_id & 0xFF
        struct.pack_into("<h", data, 13, self.p0)
        struct.pack_into("<h", data, 15, self.p1)
        struct.pack_into("<h", data, 17, self.p2)
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "ActionPacket | None":
        if len(data) != ACTION_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_ACTION:
            return None
        net_id = struct.unpack_from("<H", data, 2)[0]
        client_time_ms = struct.unpack_from("<I", data, 4)[0]
        input_seq = struct.unpack_from("<I", data, 8)[0]
        action_id = data[12]
        p0 = struct.unpack_from("<h", data, 13)[0]
        p1 = struct.unpack_from("<h", data, 15)[0]
        p2 = struct.unpack_from("<h", data, 17)[0]
        return ActionPacket(net_id, client_time_ms, input_seq, action_id, p0, p1, p2)


# ---------------------------------------------------------------------- #
# 0x05 GAME_EVENT（伺服器 → 客戶端的遊戲事件，表現層使用）
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class GameEventPacket:
    event: int
    server_tick: int
    p0: int = 0
    p1: int = 0

    def encode(self) -> bytes:
        data = bytearray(GAME_EVENT_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_GAME_EVENT
        struct.pack_into("<H", data, 2, self.event & 0xFFFF)
        struct.pack_into("<I", data, 4, self.server_tick & 0xFFFFFFFF)
        struct.pack_into("<I", data, 8, self.p0 & 0xFFFFFFFF)
        struct.pack_into("<I", data, 12, self.p1 & 0xFFFFFFFF)
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "GameEventPacket | None":
        if len(data) != GAME_EVENT_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_GAME_EVENT:
            return None
        event = struct.unpack_from("<H", data, 2)[0]
        tick = struct.unpack_from("<I", data, 4)[0]
        p0 = struct.unpack_from("<I", data, 8)[0]
        p1 = struct.unpack_from("<I", data, 12)[0]
        return GameEventPacket(event=event, server_tick=tick, p0=p0, p1=p1)


# ---------------------------------------------------------------------- #
# 0x06 MATCH_STATE（伺服器 → 客戶端的對戰狀態：回合/經濟/Spike）
# 布局（36B）：
#   [0]magic [1]type  [2:6]server_tick u32  [6]phase u8  [7]round u8
#   [8:10]round_timer_ms u16  [10]spike_state u8  [11]spike_fuse_s u8
#   [12]score_a u8  [13]score_b u8  [14]attacker_team u8  [15]reserved u8
#   [16:36] 10 × u16 credits（每槽位）
# ---------------------------------------------------------------------- #
PHASE_BUY = 0
PHASE_ACTION = 1
PHASE_END = 2
PHASE_FINISHED = 3

SPIKE_IDLE = 0
SPIKE_PLANTING = 1
SPIKE_PLANTED = 2
SPIKE_DEFUSING = 3
SPIKE_DETONATED = 4
SPIKE_DEFUSED = 5


@dataclass(frozen=True, slots=True)
class MatchStatePacket:
    server_tick: int
    phase: int
    round: int
    round_timer_ms: int
    spike_state: int
    spike_fuse_s: int
    score_a: int
    score_b: int
    attacker_team: int
    credits: tuple = ()          # 每槽位 credits（10 個）

    def encode(self) -> bytes:
        data = bytearray(MATCH_STATE_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_MATCH_STATE
        struct.pack_into("<I", data, 2, self.server_tick & 0xFFFFFFFF)
        data[6] = self.phase & 0xFF
        data[7] = self.round & 0xFF
        struct.pack_into("<H", data, 8, clamp(self.round_timer_ms, 0, 65535) & 0xFFFF)
        data[10] = self.spike_state & 0xFF
        data[11] = clamp(self.spike_fuse_s, 0, 255) & 0xFF
        data[12] = clamp(self.score_a, 0, 255) & 0xFF
        data[13] = clamp(self.score_b, 0, 255) & 0xFF
        data[14] = self.attacker_team & 0xFF
        for i in range(10):
            c = int(self.credits[i]) if i < len(self.credits) else 0
            struct.pack_into("<H", data, 16 + i * 2, clamp(c, 0, 65535) & 0xFFFF)
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "MatchStatePacket | None":
        if len(data) != MATCH_STATE_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_MATCH_STATE:
            return None
        tick = struct.unpack_from("<I", data, 2)[0]
        phase = data[6]
        round_ = data[7]
        timer = struct.unpack_from("<H", data, 8)[0]
        spike = data[10]
        fuse = data[11]
        sa = data[12]
        sb = data[13]
        atk = data[14]
        credits = tuple(struct.unpack_from("<H", data, 16 + i * 2)[0] for i in range(10))
        return MatchStatePacket(tick, phase, round_, timer, spike, fuse, sa, sb, atk, credits)


@dataclass(frozen=True, slots=True)
class AbilityStatePacket:
    """0x07 ABILITY_STATE — 伺服器廣播各玩家的技能狀態（每秒；含終點球充能）。

    為什麼放這個封包而不是 SnapshotPacket：後座/命中是 20Hz 熱路徑且已被 parity 鎖死，
    而技能充能變化很慢（擊殺才 +2），塞進 snapshot 會把每 tick 的位元組數放大 40 倍。
    這裡是「狀態」而非「事件」→ 遺失一個封包也只延遲 1 秒更新，不會錯值。

    每人 8 bytes（header 6B 之後，依 slot 排列）：
        +0..3  四槽冷卻剩餘（0.1s 單位，上限 25.5s）—— 與舊版語意完全相同
        +4     終點球點數（0..15）
        +5     終點球所需點數（0 = 這角沒有終點球）
        +6     各槽剩餘使用次數，2 bits/槽（bit0-1=Q, 2-3=E, 4-5=C, 6-7=X）
        +7     旗標：bit0 終點球就緒、bit1 技能被壓制（KAY/O 致盲式封鎖）
    """
    server_tick: int
    states: tuple  # 10 × 8 個 int

    def encode(self) -> bytes:
        data = bytearray(ABILITY_STATE_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_ABILITY_STATE
        struct.pack_into("<I", data, 2, self.server_tick & 0xFFFFFFFF)
        for slot in range(MAX_SLOTS):
            st = self.states[slot] if slot < len(self.states) else (0,) * ABILITY_STATE_ENTRY_SIZE
            off = 6 + slot * ABILITY_STATE_ENTRY_SIZE
            for a in range(ABILITY_STATE_ENTRY_SIZE):
                data[off + a] = int(st[a] if a < len(st) else 0) & 0xFF
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "AbilityStatePacket | None":
        if len(data) != ABILITY_STATE_PACKET_SIZE or data[0] != MAGIC or data[1] != TYPE_ABILITY_STATE:
            return None
        tick = struct.unpack_from("<I", data, 2)[0]
        states = []
        for slot in range(MAX_SLOTS):
            off = 6 + slot * ABILITY_STATE_ENTRY_SIZE
            states.append(tuple(data[off + a] for a in range(ABILITY_STATE_ENTRY_SIZE)))
        return AbilityStatePacket(tick, tuple(states))

    # ---- 客戶端友善取窗 ---- #
    @staticmethod
    def cooldowns_of(entry: tuple) -> tuple[float, ...]:
        return tuple(entry[a] / 10.0 for a in range(4))

    @staticmethod
    def charges_of(entry: tuple) -> tuple[int, ...]:
        return tuple((entry[6] >> (i * 2)) & 0x3 for i in range(4))

    @staticmethod
    def ult_of(entry: tuple) -> tuple[int, int, bool, bool]:
        """(點數, 所需, 就緒, 被壓制)。"""
        return (entry[4], entry[5], bool(entry[7] & 1), bool(entry[7] & 2))


@dataclass(frozen=True, slots=True)
class WorldStatePacket:
    """0x09 WORLD_STATE — 煙霧位置/半徑/剩餘時間（供客戶端體積霧渲染）。

    格式：
      [0]magic [1]type  [2:6]server_tick u32  [6]smoke_count u8  [7]reserved u8
      per-smoke (14 B)： pos_xyz i16 (×0.01 m) | radius i16 (×0.01 m) |
                        time_left u8 (×0.25s，max 63.75s) | team u8 | reserved u8 | reserved u8
    最多 8 個煙霧（競技模式中同時超過 8 個極罕見）。
    """
    server_tick: int
    smokes: tuple  # tuple of (x, y, z, radius, time_left_s, team)

    def encode(self) -> bytes:
        data = bytearray(WORLD_STATE_PACKET_SIZE)
        data[0] = MAGIC
        data[1] = TYPE_WORLD_STATE
        struct.pack_into("<I", data, 2, self.server_tick & 0xFFFFFFFF)
        count = min(len(self.smokes), MAX_WORLD_SMOKES)
        data[6] = count & 0xFF
        for i in range(count):
            s = self.smokes[i]
            off = WORLD_STATE_HEADER_SIZE + i * WORLD_STATE_SMOKE_ENTRY_SIZE
            struct.pack_into("<hhh", data, off, _q16(s[0]), _q16(s[1]), _q16(s[2]))
            struct.pack_into("<H", data, off + 6, clamp(int(s[3] * 100), 0, 65535) & 0xFFFF)
            data[off + 8] = clamp(int(s[4] * 4.0), 0, 255) & 0xFF  # time_left ×4 (0.25s res)
            data[off + 9] = int(s[5]) & 0xFF  # team
        return bytes(data)

    @staticmethod
    def decode(data: bytes) -> "WorldStatePacket | None":
        if len(data) < WORLD_STATE_HEADER_SIZE or data[0] != MAGIC or data[1] != TYPE_WORLD_STATE:
            return None
        tick = struct.unpack_from("<I", data, 2)[0]
        count = data[6]
        smokes = []
        for i in range(min(count, MAX_WORLD_SMOKES)):
            off = WORLD_STATE_HEADER_SIZE + i * WORLD_STATE_SMOKE_ENTRY_SIZE
            if off + WORLD_STATE_SMOKE_ENTRY_SIZE > len(data):
                break
            x, y, z = struct.unpack_from("<hhh", data, off)
            r = struct.unpack_from("<H", data, off + 6)[0] * _QUANT
            time_left = data[off + 8] / 4.0
            team = data[off + 9]
            smokes.append((_unq16(x), _unq16(y), _unq16(z), r, time_left, team))
        return WorldStatePacket(tick, tuple(smokes))


def weapon_item_id(item_id: int) -> str | None:
    """購買選單的 item id → 武器 key（9000=輕甲、9001=重甲）。"""
    if item_id >= 9000:
        return None
    from server.game.weapons import WEAPONS

    keys = sorted(WEAPONS)
    if 0 <= item_id < len(keys):
        return keys[item_id]
    return None
