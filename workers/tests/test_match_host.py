"""
本機測試 MatchHost（Workers-agnostic 核心）：
  * welcome / 快照廣播流程
  * 確定性（同 seed 同輸入 → 位元組一致快照）
  * AI 觀戰模式（空槽 AI 補位、比賽推進、擊殺發生）
  * 斷線釋放槽位
  * 反作弊仍生效（輸入洪水 → 踢除）
"""

from __future__ import annotations

import sys

sys.path.insert(0, "..")  # noqa: 讓 src 模組可直接 import（conftest 已處理，保險）

from match_host import MatchHost  # noqa: E402
from server.core.movement import MoveInput  # noqa: E402
from server.netcode.protocol import (  # noqa: E402
    ACTION_PACKET_SIZE,
    INPUT_PACKET_SIZE,
    SNAPSHOT_PACKET_SIZE,
    WELCOME_PACKET_SIZE,
    ActionPacket,
    InputPacket,
    SnapshotPacket,
    WelcomePacket,
)


class FakeClock:
    def __init__(self, t0: float = 0.0):
        self.t = t0

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Sink:
    """收集 (ws_id, data) 出站資料。"""

    def __init__(self):
        self.frames: list[tuple[int, bytes]] = []

    def __call__(self, ws_id: int, data: bytes):
        self.frames.append((ws_id, data))


def _input(seq: int, forward: float = 0.0, strafe: float = 0.0) -> bytes:
    return InputPacket(net_id=1, input_seq=seq, client_time_ms=1,
                       move=MoveInput(forward=forward, strafe=strafe)).encode()


def _frames_for(sink: Sink, ws_id: int) -> list[bytes]:
    return [d for w, d in sink.frames if w == ws_id]


def _new_host(seed=1, ai_mode=False, t0=0.0) -> tuple[MatchHost, Sink, FakeClock]:
    clock = FakeClock(t0)
    sink = Sink()
    host = MatchHost(seed=seed, ai_mode=ai_mode, on_send=sink, now_fn=clock.now)
    return host, sink, clock


def test_welcome_then_snapshot_flow():
    host, sink, clock = _new_host(seed=1)

    ws_id = host.connect()
    assert host.session_count() == 0

    # 第一個封包 → 建立 session → welcome 送出（dt=0 → 尚無 tick）
    host.on_message(ws_id, _input(1, forward=1.0))
    assert host.session_count() == 1
    frames = _frames_for(sink, ws_id)
    assert frames, "應收到出站資料"
    assert WelcomePacket.decode(frames[0]) is not None, "第一個封包應是 welcome"

    # 推進 1 秒 → 128 tick → 快照出現
    clock.advance(1.0)
    n = host.advance()
    assert n == 128
    snaps = [f for f in _frames_for(sink, ws_id) if f[1] == 0x02]
    assert snaps, "1 秒後應有快照"
    snap = SnapshotPacket.decode(snaps[-1])
    assert snap is not None and snap.server_tick >= 1
    assert snap.state_for_slot(0) is not None and snap.state_for_slot(0).occupied

    # 走過買槍期（首回合 45s，移動凍結）→ 進入 ACTION 後移動生效
    for _ in range(46):
        clock.advance(1.0)
        host.advance()
    p0 = host.world.players[0].pos
    for _ in range(128):
        host.on_message(ws_id, _input(seq=1000 + _, forward=1.0))
        clock.advance(8 / 128)
        host.advance()
    all_frames = _frames_for(sink, ws_id)
    snaps2 = [f for f in all_frames if len(f) > 1 and f[1] == 0x02]
    assert snaps2, "移動後應有快照"
    snap2 = SnapshotPacket.decode(snaps2[-1])
    assert snap2 is not None, "快照解碼失敗"
    moved = (snap2.state_for_slot(0).pos - p0).length()
    assert moved > 0.5, f"ACTION 期 forward=1 應移動（位移 {moved:.2f}m；出生點附近有掩體牆，撞牆即停）"


def test_determinism_same_seed():
    def run() -> bytes:
        host, sink, clock = _new_host(seed=7)
        host.connect()
        for seq in range(1, 200):
            host.on_message(1, _input(seq, forward=0.5, strafe=0.25))
            clock.advance(8 / 128)
            host.advance()
        return _frames_for(sink, 1)[-1]

    assert run() == run()


def test_ai_mode_progresses_and_fights():
    host, sink, clock = _new_host(seed=2024, ai_mode=True)
    ws_id = host.connect()
    host.on_message(ws_id, _input(1))  # 觀戰者送輸入註冊（與 UDP 行為一致：無 session 不收快照）

    # 跑約 150 秒遊戲時間（買槍期 30s + 行動期 120s）
    for _ in range(150):
        clock.advance(1.0)
        host.advance()
    assert host.server.tick > 1000

    total_kills = sum(p.kills for p in host.world.players)
    assert total_kills > 0, "AI 對戰應產生擊殺"
    assert host.world.match.round >= 1
    # 觀戰者持續收到快照
    assert _frames_for(sink, 1)


def test_slot_reuse_after_close():
    host, sink, clock = _new_host(seed=3)

    a = host.connect()
    host.on_message(a, _input(1))
    assert host.session_count() == 1

    host.on_close(a)
    assert host.session_count() == 0

    b = host.connect()
    host.on_message(b, _input(1))
    assert host.session_count() == 1
    sess = next(iter(host.server.sessions.values()))
    assert sess.slot == 0, "斷線釋放的槽位應被重用"


def test_anticheat_input_flood_kicks():
    host, sink, clock = _new_host(seed=5)
    ws_id = host.connect()

    # 短時間內灌入 2000 個輸入（遠超 170/s 上限）→ 累計違規 → 踢除
    host.on_message(ws_id, _input(1))
    for seq in range(2, 2000):
        host.server.ingest(ws_id, _input(seq))
    assert host.session_count() == 0, "洪水應觸發 INPUT_FLOOD 踢除"


def test_action_shoot_reduces_magazine():
    """ACTION 封包（射擊）經 WS 路徑執行：快照彈匣減少（伺服器權威）。"""
    host, sink, clock = _new_host(seed=9)
    ws_id = host.connect()
    host.on_message(ws_id, _input(1))

    # 走過買槍期 → 行動期
    for _ in range(46):
        clock.advance(1.0)
        host.advance()

    from server.netcode.protocol import ActionPacket, ACTION_SHOOT

    mag_before = host.world.players[0].weapon.mag
    assert mag_before > 0
    # 連發 3 槍（每槍都要先送輸入建立 seq 對應）
    for i in range(3):
        host.on_message(ws_id, _input(100 + i))
        host.server.ingest(ws_id, ActionPacket(net_id=1, client_time_ms=1, input_seq=100 + i,
                                               action_id=ACTION_SHOOT, p0=0, p1=0).encode())
        clock.advance(8 / 128)
        host.advance()
    mag_after = host.world.players[0].weapon.mag
    assert mag_after < mag_before, f"射擊應消耗彈匣 {mag_before} → {mag_after}"
    # 快照中也反映新彈匣
    last_snap = SnapshotPacket.decode(_frames_for(sink, ws_id)[-1])
    assert last_snap.state_for_slot(0).mag < mag_before


def test_packet_sizes_match_protocol():
    # 確保 WS 版的封包與 UDP 版位元組格式一致
    assert InputPacket(net_id=1, input_seq=1, client_time_ms=1,
                       move=MoveInput()).encode().__len__() == INPUT_PACKET_SIZE
    assert ActionPacket(net_id=1, client_time_ms=1, input_seq=1,
                        action_id=1).encode().__len__() == ACTION_PACKET_SIZE
    assert WelcomePacket(net_id=1, slot=0).encode().__len__() == WELCOME_PACKET_SIZE
    assert len(SnapshotPacket(server_tick=1, entries=[]).encode()) == SNAPSHOT_PACKET_SIZE
