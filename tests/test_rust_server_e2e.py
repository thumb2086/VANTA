"""M5/M6 純 Rust 伺服器（vanta_server）：selftest（移動+射擊命中）+
E2E（協定互通：welcome/移動/開火執行）+ 基準。"""

import os
import socket
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BIN = os.path.join(ROOT, "rust", "bin", "vanta_server")
pytestmark = pytest.mark.skipif(not os.path.isfile(BIN), reason="vanta_server 未建置（先跑 scripts/setup_rust.sh）")


def _pick_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --------------------------------------------------------------------- #
# selftest（不經 socket：移動 / 近距射擊 / 遠距射擊 全命中）
# --------------------------------------------------------------------- #
def test_selftest():
    r = subprocess.run([BIN, "--selftest"], capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "移動 OK" in r.stdout
    assert "射擊/擊殺 OK" in r.stdout


# --------------------------------------------------------------------- #
# E2E：welcome → 移動 → 開火執行（mag 減少）
# --------------------------------------------------------------------- #
@pytest.fixture()
def rust_server():
    port = _pick_port()
    proc = subprocess.Popen([BIN, "--port", str(port), "--seconds", "12", "--fast"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()


def _register(port):
    from server.core.movement import MoveInput
    from server.netcode.protocol import InputPacket, WelcomePacket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.2)
    w, seq = None, 0
    for _ in range(200):
        s.sendto(InputPacket(net_id=0, input_seq=seq, client_time_ms=1,
                             move=MoveInput()).encode(), ("127.0.0.1", port))
        seq += 1
        try:
            d, _ = s.recvfrom(1024)
            if len(d) > 1 and d[0] == 0x56 and d[1] == 0x03:
                w = WelcomePacket.decode(d)
                break
        except socket.timeout:
            pass
        time.sleep(0.002)
    return s, w


def _snap(sock):
    """讀最新快照（清空 buffer，避免讀到舊的）。"""
    from server.netcode.protocol import SnapshotPacket

    latest = None
    for _ in range(50):
        try:
            d, _ = sock.recvfrom(1024)
            if len(d) > 1 and d[1] == 0x02:
                latest = SnapshotPacket.decode(d)
        except socket.timeout:
            break
    return latest


def test_e2e_welcome_move_fire(rust_server):
    """E2E：welcome + B 移動 + A 開火（伺服器執行，mag 減少）。"""
    from server.core.movement import MoveInput
    from server.netcode.protocol import ActionPacket, ACTION_SHOOT, InputPacket

    port = rust_server
    a, wa = _register(port)                       # A → slot0（攻）
    dummies = [_register(port) for _ in range(4)]  # 4 個攻方 dummy（避免守方無人→立即全滅）
    b, wb = _register(port)                       # B → slot5（守）
    assert wa and wb
    assert wa.slot < 5 and wb.slot >= 5, f"分隊錯誤: A={wa.slot} B={wb.slot}"

    # 等 BUY 階段結束 → ACTION（輪詢 MATCH_STATE，不靠 sleep——沙箱 sleep 不準）
    from server.netcode.protocol import MatchStatePacket
    t0 = time.time()
    phase = -1
    while time.time() - t0 < 6:
        a.sendto(InputPacket(net_id=wa.net_id, input_seq=99999, client_time_ms=1,
                             move=MoveInput()).encode(), ("127.0.0.1", port))
        for _ in range(10):
            try:
                d, _ = a.recvfrom(1024)
                if len(d) > 1 and d[1] == 0x06:
                    phase = MatchStatePacket.decode(d).phase
                    break
                if len(d) > 1 and d[1] == 0x02:
                    break
            except socket.timeout:
                break
        if phase == 1:
            break
        time.sleep(0.05)
    assert phase == 1, f"未進入 ACTION（phase={phase}）"

    # B 移動（每 tick 1 個輸入 → 伺服器 128Hz 消費）
    for i in range(400):
        b.sendto(InputPacket(net_id=wb.net_id, input_seq=1000 + i, client_time_ms=1,
                             move=MoveInput(forward=1.0)).encode(), ("127.0.0.1", port))
        time.sleep(0.001)

    # B 的 z 應明顯前進（>1m；沙箱 sleep 不準但每 tick 消費正確）
    bz = None
    for _ in range(10):
        snap = _snap(b)
        if snap:
            e = snap.state_for_slot(wb.slot)
            if e:
                bz = e.pos.z
                break
    assert bz is not None and bz > 1.0, f"B 未移動: z={bz}"

    # A 開火 → 伺服器執行（快照 mag 減少）
    amag_before = None
    for _ in range(10):
        snap = _snap(a)
        if snap:
            e = snap.state_for_slot(wa.slot)
            if e:
                amag_before = e.mag
                break
    assert amag_before is not None and amag_before > 0
    for _ in range(30):
        a.sendto(InputPacket(net_id=wa.net_id, input_seq=2000, client_time_ms=1,
                             move=MoveInput()).encode(), ("127.0.0.1", port))
        a.sendto(ActionPacket(net_id=wa.net_id, client_time_ms=1, input_seq=2000,
                              action_id=ACTION_SHOOT, p0=0, p1=0).encode(),
                 ("127.0.0.1", port))
        time.sleep(0.01)
    amag_after = None
    from server.netcode.protocol import MatchStatePacket
    ph = -1
    for _ in range(10):
        snap = _snap(a)
        if snap:
            e = snap.state_for_slot(wa.slot)
            if e:
                amag_after = e.mag
        try:
            d, _ = a.recvfrom(1024)
            if len(d) > 1 and d[1] == 0x06:
                ph = MatchStatePacket.decode(d).phase
        except socket.timeout:
            pass
    assert amag_after is not None
    assert amag_after < amag_before, f"開火未執行: mag {amag_before}→{amag_after}"
    print(f"✅ E2E: welcome/移動/開火執行 (B z={bz:.1f}, mag {amag_before}→{amag_after})")


# --------------------------------------------------------------------- #
# 基準
# --------------------------------------------------------------------- #
def test_rust_server_binary_benchmark():
    """基準：128Hz 10 玩家，每 tick < 10µs（即時倍率 > 800x）。"""
    r = subprocess.run([BIN, "--port", "0", "--bench-ticks", "76800"],
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    import re

    m = re.search(r"每 tick ([0-9.]+) µs", r.stdout)
    assert m, r.stdout
    us = float(m.group(1))
    assert us < 10.0, f"每 tick {us}µs 超標"
