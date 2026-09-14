"""Godot 客戶端 ↔ Python 伺服器：協定常數一致性測試。

防止 GDScript 與 Python 的封包格式/事件碼漂移（Godot 客戶端依賴此對齊）。
從 client/scripts/net_client.gd 抽取常數，與 server/netcode/protocol.py 比對。
"""

import re

from server.netcode import protocol as py


def _gd_consts() -> dict[str, int]:
    """從 net_client.gd 抽取 const 定義（支援常數間的算術表達式）。"""
    path = "client/scripts/net_client.gd"
    with open(path, encoding="utf-8") as f:
        src = f.read()
    out: dict[str, int] = {}
    for m in re.finditer(r"const\s+(\w+)\s*:?=\s*([^\n]+)", src):
        name, expr = m.group(1), m.group(2).strip()
        # 安全求值：只用已定義的整數常數
        try:
            out[name] = eval(expr, {"__builtins__": {}}, dict(out))  # noqa: S307
        except Exception:
            pass
    return out


def _py_consts() -> dict[str, int]:
    return {k: v for k, v in vars(py).items() if isinstance(v, int)}


def test_packet_sizes_match():
    gd = _gd_consts()
    assert gd["INPUT_SIZE"] == py.INPUT_PACKET_SIZE
    assert gd["WELCOME_SIZE"] == py.WELCOME_PACKET_SIZE
    assert gd["SNAPSHOT_HEADER"] == py.SNAPSHOT_HEADER_SIZE
    assert gd["SNAPSHOT_ENTRY"] == py.SNAPSHOT_ENTRY_SIZE
    assert gd["MAX_SLOTS"] == py.MAX_SLOTS
    assert gd["SNAPSHOT_SIZE"] == py.SNAPSHOT_PACKET_SIZE


def test_types_match():
    gd = _gd_consts()
    assert gd["MAGIC"] == py.MAGIC
    assert gd["TYPE_INPUT"] == py.TYPE_INPUT
    assert gd["TYPE_SNAPSHOT"] == py.TYPE_SNAPSHOT
    assert gd["TYPE_WELCOME"] == py.TYPE_WELCOME
    assert gd["TYPE_GAME_EVENT"] == py.TYPE_GAME_EVENT


def test_game_event_codes_match():
    gd = _gd_consts()
    for name in ("EV_KILL", "EV_SPIKE_PLANTED", "EV_SPIKE_DEFUSED",
                 "EV_SPIKE_DETONATED", "EV_ROUND_WIN", "EV_ROUND_LOSS", "EV_MATCH_END"):
        assert gd[name] == getattr(py, name), name


def test_action_codes_match():
    gd = _gd_consts()
    assert gd["ACTION_SHOOT"] == py.ACTION_SHOOT
    assert gd["ACTION_RELOAD"] == py.ACTION_RELOAD


def test_snapshot_field_offsets_match_layout():
    """驗證 GDScript 使用的快照偏移與 Python 序列化布局一致。"""
    gd = _gd_consts()
    assert gd["SNAPSHOT_HEADER"] + gd["MAX_SLOTS"] * gd["SNAPSHOT_ENTRY"] == gd["SNAPSHOT_SIZE"]
    # Python 側：health/mag 於 offset+22/23、武器槽位 +24、換彈進度 +25
    assert py.SNAPSHOT_ENTRY_SIZE == 26
    assert gd["SNAPSHOT_ENTRY"] == 26
