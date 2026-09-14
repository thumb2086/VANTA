"""M2 封包協定（序列化/反序列化）測試。"""

import math

import pytest

from server.core.movement import MoveInput
from server.netcode.protocol import (
    INPUT_PACKET_SIZE,
    SNAPSHOT_ENTRY_SIZE,
    SNAPSHOT_HEADER_SIZE,
    SNAPSHOT_PACKET_SIZE,
    WELCOME_PACKET_SIZE,
    InputPacket,
    SnapshotEntry,
    SnapshotPacket,
    WelcomePacket,
)
from server.core.math_core import Vec3


# --------------------------------------------------------------------- #
# 輸入封包
# --------------------------------------------------------------------- #
def test_input_round_trip():
    pkt = InputPacket(
        net_id=7,
        input_seq=12345,
        client_time_ms=67890,
        move=MoveInput(forward=0.5, strafe=-1.0, walk=True, crouch=False, jump=True),
    )
    raw = pkt.encode()
    assert len(raw) == INPUT_PACKET_SIZE
    dec = InputPacket.decode(raw)
    assert dec is not None
    assert dec.net_id == 7
    assert dec.input_seq == 12345
    assert dec.client_time_ms == 67890
    assert math.isclose(dec.move.forward, 0.5, abs_tol=1 / 127 + 1e-6)
    assert math.isclose(dec.move.strafe, -1.0, abs_tol=1e-6)
    assert dec.move.walk is True
    assert dec.move.crouch is False
    assert dec.move.jump is True


def test_input_bad_packet_rejected():
    assert InputPacket.decode(b"\x00" * INPUT_PACKET_SIZE) is None   # 錯 magic
    assert InputPacket.decode(b"\x56\x99" + b"\x00" * 13) is None    # 錯 type
    assert InputPacket.decode(b"\x56\x01" + b"\x00" * 10) is None    # 長度不足


def test_input_quantization_bounds():
    """極端類比值夾取：2.0 → 127，-2.0 → -127。"""
    pkt = InputPacket(1, 0, 0, MoveInput(forward=2.0, strafe=-2.0))
    dec = InputPacket.decode(pkt.encode())
    assert dec.move.forward == 1.0
    assert dec.move.strafe == -1.0


# --------------------------------------------------------------------- #
# 快照封包
# --------------------------------------------------------------------- #
def test_snapshot_round_trip():
    entries = [
        SnapshotEntry(
            slot=0,
            pos=Vec3(12.345, 0.0, -7.891),
            vel=Vec3(5.43, -2.1, 0.0),
            on_ground=True,
            crouching=False,
            walking=True,
            occupied=True,
            echo_client_time_ms=999,
            health=87,
            mag=12,
            reloading=True,
            weapon_slot=0,
            reload_progress=127,
        ),
        SnapshotEntry(
            slot=3,
            pos=Vec3(-30.0, 1.5, 20.25),
            vel=Vec3(),
            on_ground=False,
            crouching=True,
            walking=False,
            occupied=True,
            echo_client_time_ms=42,
            health=100,
            mag=30,
            reloading=False,
            weapon_slot=2,
        ),
    ]
    snap = SnapshotPacket(server_tick=2048, entries=entries)
    raw = snap.encode()
    assert len(raw) == SNAPSHOT_PACKET_SIZE
    assert SNAPSHOT_PACKET_SIZE == SNAPSHOT_HEADER_SIZE + 10 * SNAPSHOT_ENTRY_SIZE

    dec = SnapshotPacket.decode(raw)
    assert dec is not None
    assert dec.server_tick == 2048
    assert len(dec.entries) == 2

    e0 = dec.state_for_slot(0)
    assert e0 is not None
    assert math.isclose(e0.pos.x, 12.34, abs_tol=0.011)      # 0.01 量化
    assert math.isclose(e0.pos.y, 0.0, abs_tol=0.011)
    assert math.isclose(e0.pos.z, -7.89, abs_tol=0.011)
    assert math.isclose(e0.vel.x, 5.43, abs_tol=0.011)
    assert math.isclose(e0.vel.y, -2.10, abs_tol=0.011)
    assert e0.on_ground is True
    assert e0.walking is True
    assert e0.echo_client_time_ms == 999
    assert e0.health == 87
    assert e0.mag == 12
    assert e0.reloading is True
    assert e0.weapon_slot == 0
    assert e0.reload_progress == 127
    assert dec.echo_for_slot(0) == 999
    assert dec.state_for_slot(1) is None     # 未佔用槽位
    e3 = dec.state_for_slot(3)
    assert e3.weapon_slot == 2
    assert e3.reloading is False
    assert e3.reload_progress == 255          # 未換彈


def test_snapshot_empty_slots_skipped():
    snap = SnapshotPacket(server_tick=1, entries=[])
    dec = SnapshotPacket.decode(snap.encode())
    assert dec is not None
    assert dec.entries == []
    assert dec.state_for_slot(9) is None


def test_snapshot_bad_packet_rejected():
    assert SnapshotPacket.decode(b"\x00" * SNAPSHOT_PACKET_SIZE) is None
    assert SnapshotPacket.decode(b"\x56\x99" + b"\x00" * 100) is None


# --------------------------------------------------------------------- #
# 歡迎封包
# --------------------------------------------------------------------- #
def test_welcome_round_trip():
    w = WelcomePacket(net_id=5, slot=3)
    raw = w.encode()
    assert len(raw) == WELCOME_PACKET_SIZE
    dec = WelcomePacket.decode(raw)
    assert dec is not None
    assert dec.net_id == 5
    assert dec.slot == 3


def test_welcome_bad_rejected():
    assert WelcomePacket.decode(b"\x00" * WELCOME_PACKET_SIZE) is None
    assert WelcomePacket.decode(b"\x56\x03\x00") is None     # 長度不足


# --------------------------------------------------------------------- #
# 行動封包
# --------------------------------------------------------------------- #
def test_action_round_trip():
    from server.netcode.protocol import ACTION_SHOOT, ActionPacket, ACTION_PACKET_SIZE

    act = ActionPacket(net_id=3, client_time_ms=12345, input_seq=678,
                       action_id=ACTION_SHOOT, p0=1234, p1=-567, p2=0)
    raw = act.encode()
    assert len(raw) == ACTION_PACKET_SIZE
    dec = ActionPacket.decode(raw)
    assert dec is not None
    assert dec.net_id == 3
    assert dec.client_time_ms == 12345
    assert dec.input_seq == 678
    assert dec.action_id == ACTION_SHOOT
    assert dec.p0 == 1234
    assert dec.p1 == -567


def test_action_bad_rejected():
    from server.netcode.protocol import ActionPacket

    assert ActionPacket.decode(b"\x00" * 19) is None
    assert ActionPacket.decode(b"\x56\x99" + b"\x00" * 17) is None


def test_snapshot_last_input_seq_round_trip():
    snap = SnapshotPacket(server_tick=5, entries=[
        SnapshotEntry(slot=2, pos=Vec3(1, 0, 2), vel=Vec3(), on_ground=True,
                      crouching=False, walking=False, occupied=True,
                      echo_client_time_ms=10, last_input_seq=77,
                      reloading=True, weapon_slot=2),
    ])
    dec = SnapshotPacket.decode(snap.encode())
    e = dec.state_for_slot(2)
    assert e.last_input_seq == 77
    assert e.reloading is True
    assert e.weapon_slot == 2


def test_snapshot_size_26():
    """快照條目 26B：含武器槽位 + 換彈進度；套件大小應一致。"""
    assert SNAPSHOT_ENTRY_SIZE == 26
    assert SNAPSHOT_PACKET_SIZE == SNAPSHOT_HEADER_SIZE + 10 * SNAPSHOT_ENTRY_SIZE


def test_reload_progress_round_trip():
    snap = SnapshotPacket(server_tick=9, entries=[
        SnapshotEntry(slot=4, pos=Vec3(0, 0, 0), vel=Vec3(), on_ground=True,
                      crouching=False, walking=False, occupied=True,
                      echo_client_time_ms=1, reload_progress=200),
    ])
    dec = SnapshotPacket.decode(snap.encode())
    assert dec.state_for_slot(4).reload_progress == 200


def test_action_switch_code():
    from server.netcode.protocol import ACTION_SWITCH

    assert ACTION_SWITCH == 0x07


def test_weapon_item_id_mapping():
    from server.netcode.protocol import weapon_item_id

    assert weapon_item_id(0) == "ares"      # 依字母序第一個
    assert weapon_item_id(9000) is None     # 護甲由伺服器另外處理
    assert weapon_item_id(9999) is None


# --------------------------------------------------------------------- #
# 遊戲事件封包
# --------------------------------------------------------------------- #
def test_game_event_round_trip():
    from server.netcode.protocol import (
        EV_KILL,
        GAME_EVENT_PACKET_SIZE,
        GameEventPacket,
    )

    ev = GameEventPacket(event=EV_KILL, server_tick=1234, p0=3, p1=7)
    raw = ev.encode()
    assert len(raw) == GAME_EVENT_PACKET_SIZE
    dec = GameEventPacket.decode(raw)
    assert dec is not None
    assert dec.event == EV_KILL
    assert dec.server_tick == 1234
    assert dec.p0 == 3
    assert dec.p1 == 7


def test_game_event_bad_rejected():
    from server.netcode.protocol import GameEventPacket

    assert GameEventPacket.decode(b"\x00" * 16) is None
    assert GameEventPacket.decode(b"\x56\x99" + b"\x00" * 14) is None
