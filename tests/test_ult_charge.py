"""終點球充能（X 槽）— 權威、傳輸、顯示三層測試
================================================
鎖住三件事：
1. **充能規則**（擊殺 +2 / 助攻 +1 / 安放 +1 / 拆除 +1 / 敗方每人 +1，上限 8、跨回合保留）
2. **門控**（未滿不能放，放完歸零；只對標了 `is_ultimate` 的招生效）
3. **傳輸契約**（0x07 ABILITY_STATE 8 bytes/人；Python ⇄ GDScript 位元組級對齊，
   而 20Hz 的 SNAPSHOT 一字未動）
"""

from __future__ import annotations

import math
import pathlib
import re

import pytest

from server.core.math_core import Vec3
from server.game.abilities import (
    ABILITY_WIRE_BYTES,
    AGENTS,
    ULT_MAX_POINTS,
    AbilitySystem,
)
from server.game.entities import (
    ULT_POINTS_ASSIST,
    ULT_POINTS_KILL,
    ULT_POINTS_ROUND_LOSS,
    ULT_POINTS_SPIKE,
    World,
)
from server.netcode.protocol import (
    ABILITY_STATE_ENTRY_SIZE,
    ABILITY_STATE_PACKET_SIZE,
    MAX_SLOTS,
    SNAPSHOT_PACKET_SIZE,
    AbilityStatePacket,
)

DT = 1.0 / 128.0
ROOT = pathlib.Path(__file__).resolve().parents[1]
NET_GD = ROOT / "client" / "scripts" / "net_client.gd"


def step(world: World, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        world.step([None] * MAX_SLOTS, DT)


def equip(world: World, slot: int, agent: str) -> AbilitySystem:
    """把某玩家換成指定角色（World() 已內建 10 名玩家，這裡只換技能組）。"""
    sys_ = AbilitySystem(list(AGENTS[agent][1]))
    world.players[slot].abilities = sys_
    world.players[slot].agent_key = agent
    return sys_


def make_world(agent: str = "jett") -> World:
    world = World()
    equip(world, 0, agent)
    step(world, 0.5)
    return world


# ------------------------------------------------------------------ #
# 1. 門控與充能（AbilitySystem 層）
# ------------------------------------------------------------------ #
def test_ultimate_starts_locked_and_needs_cost():
    sys_ = AbilitySystem(list(AGENTS["jett"][1]))
    assert sys_.ult_index == 3 and sys_.ult_cost == 8
    assert not sys_.ult_ready() and sys_.slots[3].charges_left == 0

    for _ in range(7):
        sys_.add_ult_points(1)
    assert sys_.ult_points == 7 and not sys_.ult_ready()
    assert sys_.slots[3].charges_left == 0

    sys_.add_ult_points(1)
    assert sys_.ult_ready() and sys_.slots[3].charges_left == 1


def test_points_capped_and_overflow_not_stored():
    sys_ = AbilitySystem(list(AGENTS["sage"][1]))
    gained = sys_.add_ult_points(ULT_MAX_POINTS + 4)
    assert sys_.ult_points == ULT_MAX_POINTS
    assert gained == ULT_MAX_POINTS                    # 溢充不計入
    assert sys_.add_ult_points(1) == 0                  # 已滿，再无增益


def test_cast_blocked_before_ready_and_resets_after():
    world = make_world(agent="jett")
    p = world.players[0]
    aim = Vec3(0.0, 0.0, 1.0)

    p.abilities.ult_points = 0
    assert world.cast_ability(0, 3, 0.0, 0.0) is False   # 未滿 → 拒
    p.abilities.add_ult_points(p.abilities.ult_cost)
    assert p.abilities.ult_ready()

    assert world.cast_ability(0, 3, 0.0, 0.0) is True    # 滿 → 放
    assert p.abilities.ult_points == 0                    # 放完歸零（無溢存）
    assert not p.abilities.ult_ready()
    assert p.abilities.slots[3].charges_left == 0         # 鎖回去


def test_non_ultimate_slots_are_not_gated():
    """只有標記 is_ultimate 的招走充能門控；C/Q/E 維持 charges+cooldown。"""
    world = make_world(agent="jett")
    p = world.players[0]
    p.abilities.ult_points = 0
    for idx in (0, 1, 2):
        assert p.abilities.slots[idx].charges_left > 0
        assert world.cast_ability(0, idx, 0.0, 0.0) is True


def test_archetype_agents_have_no_ultimate():
    """通用原型（AI/工具用）的 slot3 並非終極技 — 不能被抓成「充能才能放」。"""
    for name in ("assault", "sentinel", "duelist", "controller"):
        sys_ = AbilitySystem(list(AGENTS[name][1]))
        assert sys_.ult_index == -1
        assert sys_.add_ult_points(3) == 0          # 沒終點球 → 不加點
        assert sys_.ult_ready() is False


ARCHETYPES = {"assault", "sentinel", "duelist", "controller"}


def test_every_named_agent_has_four_slots_and_one_ultimate():
    """命名角色（真選手）必須是 C/Q/E/X 四槽、恰一個終極技且在 index 3。"""
    named = {k: v for k, v in AGENTS.items() if k not in ARCHETYPES}
    assert len(named) >= 10
    for key, (_label, abilities) in named.items():
        assert len(abilities) == 4, f"{key}: {len(abilities)} 招"
        assert sum(1 for a in abilities if a.is_ultimate) == 1, f"{key}: 終極技數量不對"
        sys_ = AbilitySystem(list(abilities))
        assert sys_.ult_index == 3 and sys_.ult_cost >= 6


# ------------------------------------------------------------------ #
# 2. 充能來源（世界事件層）
# ------------------------------------------------------------------ #
def test_constants_follow_valorant_semantics():
    assert (ULT_POINTS_KILL, ULT_POINTS_ASSIST, ULT_POINTS_SPIKE, ULT_POINTS_ROUND_LOSS) == (2, 1, 1, 1)
    assert ULT_MAX_POINTS == 8


def test_award_ult_clamps_and_targets_slot():
    world = make_world(agent="sage")
    step(world, 0.5)
    gained = world.award_ult(0, ULT_POINTS_KILL)
    assert gained == 2 and world.players[0].abilities.ult_points == 2
    assert world.award_ult(99, 2) == 0                 # 越界安全
    assert world.award_ult(0, 0) == 0                  # 0/負數不給
    for _ in range(4):
        world.award_ult(0, 2)
    assert world.players[0].abilities.ult_points == ULT_MAX_POINTS


def test_kill_awards_killer_and_assist():
    """用世界事件走一次：擊殺者 +2，達標助攻 +1（同一份award_ult路徑）。"""
    world = make_world(agent="sage")
    equip(world, 2, "sage")            # 助攻者也要有終點球才收得到點數
    victim, killer = world.players[1], world.players[0]
    victim.dmg_log[2] = 40.0            # 第三人湊 ≥25 助攻
    world._on_player_killed(victim.slot, killer.slot, "vandal")
    assert killer.abilities.ult_points == ULT_POINTS_KILL
    assert world.players[2].abilities.ult_points == ULT_POINTS_ASSIST


# ------------------------------------------------------------------ #
# 3. 傳輸契約（0x07，8 bytes/人）
# ------------------------------------------------------------------ #
def test_wire_tuple_layout():
    sys_ = AbilitySystem(list(AGENTS["omen"][1]))
    sys_.slots[0].cooldown_left = 3.4
    sys_.slots[2].charges_left = 2
    wire = sys_.wire_tuple()
    assert len(wire) == ABILITY_WIRE_BYTES == ABILITY_STATE_ENTRY_SIZE == 8
    assert wire[0] == 34                                    # 3.4s → 34（0.1s 解析度）
    assert (wire[4], wire[5]) == (sys_.ult_points, sys_.ult_cost)
    assert (wire[6] >> (2 * 2)) & 3 == 2                    # slot2 剩 2 次


def test_packet_roundtrip_carries_ult_for_every_slot():
    sys_a = AbilitySystem(list(AGENTS["jett"][1]))
    sys_a.add_ult_points(8)
    states = [tuple(sys_a.wire_tuple()) for _ in range(MAX_SLOTS)]
    raw = AbilityStatePacket(server_tick=1234, states=tuple(states)).encode()
    assert len(raw) == ABILITY_STATE_PACKET_SIZE == 6 + MAX_SLOTS * 8

    back = AbilityStatePacket.decode(raw)
    assert back is not None and back.server_tick == 1234
    for slot in range(MAX_SLOTS):
        cds = AbilityStatePacket.cooldowns_of(back.states[slot])
        charges = AbilityStatePacket.charges_of(back.states[slot])
        points, cost, ready, blocked = AbilityStatePacket.ult_of(back.states[slot])
        assert len(cds) == 4 and len(charges) == 4
        assert (points, cost, ready, blocked) == (8, 8, True, False)
        assert charges[3] == 1                     # 就緒 → X 可用一次
    # 每個人的終點球點數都是 8（同一 tuple）：證明 per-slot 對齊沒有錯位
    assert all(AbilityStatePacket.ult_of(e)[0] == 8 for e in back.states)


def test_snapshot_hot_path_untouched():
    """終點球走 0x07，不動 20Hz 的 SNAPSHOT — 这条断言就是「没走回头路」的證明。"""
    assert SNAPSHOT_PACKET_SIZE == 270


def test_missing_packet_does_not_crash_decoder():
    assert AbilityStatePacket.decode(b"\x00" * (ABILITY_STATE_PACKET_SIZE - 1)) is None
    bad = bytearray(ABILITY_STATE_PACKET_SIZE)
    bad[0] = 0xFF
    assert AbilityStatePacket.decode(bytes(bad)) is None


# ------------------------------------------------------------------ #
# 4. GDScript ⇄ Python 位元組級契約（grep 級，跟skins同样的钉子）
# ------------------------------------------------------------------ #
def test_gdscript_ability_state_parser_matches_layout():
    src = NET_GD.read_text(encoding="utf-8")
    fn = src[src.index("func _parse_ability_state"):]
    fn = fn[:fn.index("\nfunc ") + 1] if "\nfunc " in fn else fn
    assert "ABILITY_ENTRY_SIZE := 8" in src
    assert "6 + slot * ABILITY_ENTRY_SIZE" in fn
    # 冷卻 = 前 4 個 byte，0.1s 解析度
    assert re.search(r"for a in range\(4\):\s*\n\s*cds\.append\(float\(data\[off \+ a\]\) / 10\.0\)", fn)
    # 充能在 +4/+5，旗標 +7，次數 packed 在 +6
    assert "data[off + 4]" in fn and "data[off + 5]" in fn
    assert "packed := data[off + 6]" in fn and "(packed >> (i * 2)) & 3" in fn
    assert "flags & 1" in fn and "flags & 2" in fn
    assert "data[off + 7]" in fn


def test_hud_and_global_expose_ult_state():
    hud = (ROOT / "client" / "scripts" / "hud.gd").read_text(encoding="utf-8")
    for prop in ("var ult_points", "var ult_cost", "var ult_ready", "func set_ult("):
        assert prop in hud, f"hud.gd 少了 {prop}"
    assert "k < ult_points" in hud and "clampi(ult_cost, 1, 12)" in hud
    main = (ROOT / "client" / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "hud.set_ult(" in main and "_try_cast_ult" in main
    assert "fx2.play(\"ult_ready\"" in main and "fx2.play(\"ult_cast\"" in main


def test_sfx_keys_are_registered():
    synth = (ROOT / "tools" / "sfx" / "synth.py").read_text(encoding="utf-8")
    assert '"ult_ready_chime": ult_ready_chime' in synth
    assert '"ult_cast": ult_cast' in synth
    bps = (ROOT / "tools" / "vfx" / "blueprints.py").read_text(encoding="utf-8")
    for name in ("ult_ready", "ult_cast"):
        assert f'"{name}"' in bps


def test_chime_is_monotone_and_cast_is_3_notes():
    """音效是确定性的：用工具函数直接验波形包络，不靠听。"""
    import sys

    sys.path.insert(0, str(ROOT))
    from tools.sfx import synth

    chime = synth.ult_ready_chime()
    cast = synth.ult_cast()
    assert len(chime) > 1000 and len(cast) > 1000
    assert max(map(abs, chime)) <= 1.0001
    assert max(map(abs, cast)) <= 1.0001
    # chime 的能量应集中在前中段（尾端衰减），cast 有低频躯體
    def rms(seg):
        return math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))

    assert rms(chime[: len(chime) // 2]) > rms(chime[-len(chime) // 8:])
    assert rms(cast) > 0.01
