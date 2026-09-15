"""
tests/test_fun_highlights.py — 助攻＋高光時刻驗收
=================================================
對應 docs/valorant_patch_research.md P3/P4。
* 助攻：同隊最高傷害（≥25、非兇手）+1，assist banner 事件
* 連殺播報：DOUBLE/TRIPLE/QUAD/ACE
* 殘局：勝方僅剩 1 人 → 1vX
* 首殺：每回合第一次擊殺
* POTM：整場最高分表現
"""

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.highlights import HighlightTracker, STREAK_NAMES


def _world():
    w = World()
    m = w.start_match(mode="competitive")
    return w, m


def _kill(w: World, killer: int, victim: int, dmg: float = 100.0):
    """直接傷害擊殺（經 apply_damage → 歸因＋擊殺事件）。不重置血量。"""
    w.players[victim].apply_damage(dmg, source_slot=killer, weapon_key="vandal")


def _revive_full(w: World, slot: int):
    w.players[slot].health = 100.0
    w.players[slot].alive = True


# ---------------------------------------------------------------------- #
# 助攻
# ---------------------------------------------------------------------- #
def test_assist_awarded_to_top_damager():
    w, m = _world()
    # slot0 (team0) 打 60，slot1 (team0) 補刀殺 slot5 (team1)
    _kill(w, 0, 5, dmg=60.0)
    assert w.players[5].alive  # 還沒死
    _kill(w, 1, 5, dmg=60.0)
    assert not w.players[5].alive
    assert w.players[1].kills == 1
    assert w.players[0].assists == 1, "最高傷害隊友應得助攻"
    assert any(l.startswith("assist: slot0 on slot5") for l in w.event_log)


def test_no_assist_below_threshold():
    w, m = _world()
    _kill(w, 0, 5, dmg=10.0)   # 低於 25 門檻
    _kill(w, 1, 5, dmg=100.0)
    assert w.players[0].assists == 0


def test_no_assist_for_enemy_damager():
    w, m = _world()
    # slot6 (team1，K/D 皆 team1？victim slot5 team1) — 隊友傷害不算助攻給敵方
    _kill(w, 6, 5, dmg=60.0)
    _kill(w, 0, 5, dmg=60.0)
    assert w.players[6].assists == 0
    assert w.players[0].kills == 1


def test_damage_dealt_tracked():
    w, m = _world()
    _kill(w, 0, 5, dmg=60.0)
    assert w.players[0].damage_dealt >= 60.0


def test_dmg_log_cleared_each_round():
    w, m = _world()
    _kill(w, 0, 5, dmg=60.0)
    assert w.players[5].dmg_log
    m._reset_round_state()
    assert w.players[5].dmg_log == {}


# ---------------------------------------------------------------------- #
# 高光
# ---------------------------------------------------------------------- #
def _win_round_for(w: World, m, winner_team: int):
    for p in w.players:
        if p.team != winner_team:
            p.alive = False
            p.health = 0.0
    m.phase_timer = 0.01
    for _ in range(3):
        w.step([MoveInput() for _ in w.players], 1.0 / 128.0)
    for _ in range(600):
        w.step([MoveInput() for _ in w.players], 1.0 / 128.0)


def test_streak_announcement_and_ace():
    w, m = _world()
    t = HighlightTracker()
    # slot0 連殺 team1 全員（5 殺 ACE）
    for v in (5, 6, 7, 8, 9):
        _kill(w, 0, v)
    anns = t.update(w, m)
    assert any("DOUBLE KILL" in a for a in anns)
    assert any("TRIPLE KILL" in a for a in anns)
    assert any("QUAD KILL" in a for a in anns)
    assert any("ACE" in a for a in anns), anns
    assert any("first_blood" in a for a in anns)


def test_clutch_detection():
    w, m = _world()
    t = HighlightTracker()
    t.update(w, m)  # 記錄回合開始存活數（5v5）
    # 只剩 slot0 (team0)，殺光 team1 → 1v5 殘局
    for s in (1, 2, 3, 4):
        w.players[s].alive = False
    for v in (5, 6, 7, 8, 9):
        _kill(w, 0, v)
    t.update(w, m)
    _win_round_for(w, m, 0)
    anns = t.update(w, m)
    assert any(a.startswith("clutch:") and "1v5" in a for a in anns), anns


def test_play_of_match_picks_best():
    w, m = _world()
    t = HighlightTracker()
    # R1: slot0 雙殺；R2: slot1 ACE
    for v in (5, 6):
        _kill(w, 0, v)
    t.update(w, m)
    _win_round_for(w, m, 0)
    t.update(w, m)
    for v in (5, 6, 7, 8, 9):
        for p in w.players:
            _revive_full(w, p.slot)
        _kill(w, 1, v)
    t.update(w, m)
    _win_round_for(w, m, 0)
    t.update(w, m)
    potm = t.play_of_match()
    assert potm.player == 1 and potm.streak_name == "ACE" and potm.score >= 100, potm
