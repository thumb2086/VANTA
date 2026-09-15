"""
tests/test_fun_modes.py — 快速模式驗收（Spike Rush / Swiftplay）
===============================================================
對應 docs/valorant_patch_research.md P1/P2/P7。
"""

import random

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.modes import (
    SPIKERUSH, SWIFTPLAY,
    SR_ROUNDS_TO_WIN, SR_HALF_ROUNDS, SR_SIDEARMS, SR_TIER2, SR_TIER3,
    SP_ROUNDS_TO_WIN, SP_HALF_ROUNDS,
    mode_rules, sp_round_grant, sr_round_weapon, sr_round_shield, sr_upgrade_weapon,
    OrbField, ORB_TYPES,
)


def _world(mode: str) -> tuple[World, object]:
    w = World()
    m = w.start_match(mode=mode)
    return w, m


def _step_world(w: World, n: int = 5):
    for _ in range(n):
        w.step([MoveInput() for _ in w.players], 1.0 / 128.0)


# ---------------------------------------------------------------------- #
# 規則表
# ---------------------------------------------------------------------- #
def test_mode_rules_exist():
    sr = mode_rules(SPIKERUSH)
    assert sr.rounds_to_win == SR_ROUNDS_TO_WIN == 4
    assert sr.half_rounds == SR_HALF_ROUNDS == 3
    assert sr.free_loadout and not sr.fixed_economy
    sp = mode_rules(SWIFTPLAY)
    assert sp.rounds_to_win == SP_ROUNDS_TO_WIN == 5
    assert sp.half_rounds == SP_HALF_ROUNDS == 4
    assert sp.fixed_economy and not sp.free_loadout


def test_spikerush_loadout_tiers():
    rng = random.Random(42)
    r1 = {sr_round_weapon(rng, 1) for _ in range(30)}
    assert r1 <= set(SR_SIDEARMS), r1
    r2 = {sr_round_weapon(rng, 2) for _ in range(30)}
    assert r2 <= set(SR_TIER2), r2
    r3 = {sr_round_weapon(rng, 3) for _ in range(30)}
    assert r3 <= set(SR_TIER3), r3
    assert sr_round_shield(1) == 0
    assert sr_round_shield(2) == 25
    assert sr_round_shield(3) == 50


def test_spikerush_upgrade_path():
    rng = random.Random(7)
    assert sr_upgrade_weapon(rng, "classic") in SR_TIER2
    assert sr_upgrade_weapon(rng, "spectre") in SR_TIER3
    assert sr_upgrade_weapon(rng, "vandal") in ("operator", "odin")


def test_swiftplay_economy_table():
    # 官方濃縮經濟：800 → 2400(+600) → 4250 → 4250 → 5000
    assert sp_round_grant(1, False) == 800
    assert sp_round_grant(2, False) == 2400
    assert sp_round_grant(2, True) == 3000
    assert sp_round_grant(3, False) == 4250
    assert sp_round_grant(4, True) == 4250
    assert sp_round_grant(9, False) == 5000


# ---------------------------------------------------------------------- #
# 對戰流程
# ---------------------------------------------------------------------- #
def test_spikerush_full_match_ends_at_4():
    w, m = _world(SPIKERUSH)
    # 全場同槍＋護甲
    keys = {p.inventory.active_state().stats.key for p in w.players}
    assert len(keys) == 1 and keys.pop() == m.sr_loadout
    # team0 連贏 4 回合 → 結束（每回合殺光 team1；第 4 回合換邊後殺光 team1 = 守方 team0 獲勝）
    for _ in range(7):
        for p in w.players:
            if p.team == 1:
                p.alive = False
        m.phase_timer = 0.01
        _step_world(w, 3)   # ACTION → END
        _step_world(w, 600)  # END → 下回合
        if m.phase.value == "finished":
            break
    assert m.phase.value == "finished", (m.phase, m.scores)
    assert m.scores[0] >= 4, m.scores


def test_spikerush_orbs_spawn_and_capture():
    w, m = _world(SPIKERUSH)
    assert 1 <= len(m.orb_field.orbs) <= 5
    assert all(o.kind in ORB_TYPES for o in m.orb_field.orbs)
    # 把玩家放到 orb 上 → 捕獲
    orb = m.orb_field.orbs[0]
    p = w.players[0]
    p.pos = type(p.pos)(orb.pos.x, p.pos.y, orb.pos.z)
    m.phase_timer = 999.0
    # 切到 ACTION 才能捕獲
    from server.game.match import RoundPhase
    m.phase = RoundPhase.ACTION
    evs = m.orb_field.update(w)
    assert orb.captured and orb.captured_by == 0
    assert evs and evs[0].startswith("orb: slot0")


def test_swiftplay_ends_at_5_with_fixed_economy():
    w, m = _world(SWIFTPLAY)
    assert all(p.economy.credits == 800 for p in w.players)
    for _ in range(9):
        for p in w.players:
            if p.team == 1:
                p.alive = False
        m.phase_timer = 0.01
        _step_world(w, 3)
        _step_world(w, 600)
        if m.phase.value == "finished":
            break
    assert m.phase.value == "finished", (m.phase, m.scores)
    assert m.scores[0] >= 5, m.scores


def test_swiftplay_round2_grants():
    w, m = _world(SWIFTPLAY)
    # 第 1 回合 team0 獲勝 → 第 2 回合配給：勝方 3000 / 敗方 2400
    for p in w.players:
        if p.team == 1:
            p.alive = False
    m.phase_timer = 0.01
    _step_world(w, 3)
    _step_world(w, 600)
    assert m.round == 2, (m.round, m.phase)
    t0 = [p.economy.credits for p in w.players if p.team == 0]
    t1 = [p.economy.credits for p in w.players if p.team == 1]
    assert set(t0) == {3000}, t0
    assert set(t1) == {2400}, t1


def test_quick_modes_have_spike():
    for mode in (SPIKERUSH, SWIFTPLAY):
        w, m = _world(mode)
        assert w.spike is not None, mode
