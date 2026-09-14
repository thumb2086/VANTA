"""M7/M8/M9：經濟、回合狀態機、Spike 目標測試。"""

import pytest

from server.core.math_core import Vec3
from server.game.economy import (
    CREDITS_MAX,
    KILL_REWARD,
    ROUND_WIN_REWARD,
    EconomyComponent,
    loss_bonus,
)
from server.game.entities import World
from server.game.match import Match, RoundPhase, TEAM_ATTACKERS, TEAM_DEFENDERS
from server.game.spike import (
    DEFUSE_TIME,
    FUSE_TIME,
    HALF_DEFUSE_CHECKPOINT,
    PLANT_TIME,
    SpikeController,
    SpikeState,
)

DT = 1.0 / 128.0


# --------------------------------------------------------------------- #
# 經濟（M8）
# --------------------------------------------------------------------- #
def test_loss_bonus_steps():
    assert loss_bonus(1) == 1900
    assert loss_bonus(2) == 2400
    assert loss_bonus(3) == 2900
    assert loss_bonus(10) == 2900          # 封頂


def test_economy_grant_cap():
    e = EconomyComponent(8000)
    e.grant(1500)
    assert e.credits == CREDITS_MAX        # 9000 封頂
    assert e.buy(5000)                     # 購買扣款
    assert e.credits == 4000
    assert not e.buy(5000)                 # 買不起


def test_kill_reward_and_buy():
    world = World()
    p = world.players[0]
    before = p.economy.credits
    p.apply_damage(9999, source_slot=1, weapon_key="knife")   # 殺死 p0？不，方向錯了
    # 正確：p0 殺死 p1
    world.players[1].apply_damage(9999, source_slot=0, weapon_key="vandal")
    assert world.players[0].economy.credits == before + KILL_REWARD
    assert world.players[0].kills == 1
    assert not world.players[1].alive
    assert world.players[1].deaths == 1


def test_buy_weapon_and_shield():
    world = World()
    p = world.players[0]
    p.economy.grant(10000)                       # grant 有 9000 上限
    assert p.economy.credits == 9000
    assert p.buy_weapon("vandal")
    assert p.weapon.stats.key == "vandal"
    assert p.economy.credits == 9000 - 2900      # 6100
    p.buy_shield(2)
    assert p.economy.credits == 5100
    assert p.shield_hp == 50
    # 護甲吸收
    world.players[1].pos = Vec3(0, 0, 5)
    hp_before = p.health
    p.apply_damage(60)
    assert p.shield_hp == 0
    assert p.health == hp_before - 10


# --------------------------------------------------------------------- #
# 回合狀態機（M7）
# --------------------------------------------------------------------- #
def _match_world():
    world = World()
    match = world.start_match()
    return world, match


def test_round_phases_and_win():
    world, match = _match_world()
    assert match.phase == RoundPhase.BUY
    assert match.round == 1
    assert match.attackers() == TEAM_ATTACKERS
    # 購買期結束 → 行動期
    for _ in range(int(30.0 / DT) + 1):
        world.step([None] * 10, DT)
    assert match.phase == RoundPhase.ACTION
    # 全滅防守方 → 攻方勝
    for s in range(5, 10):
        world.players[s].apply_damage(9999, source_slot=0, weapon_key="vandal")
    world.step([None] * 10, DT)
    assert match.phase == RoundPhase.END
    assert match.round_winner == TEAM_ATTACKERS
    assert match.scores[TEAM_ATTACKERS] == 1
    # 結算 → 下一回合購買期，經濟發放
    for _ in range(int(4.0 / DT)):
        world.step([None] * 10, DT)
    assert match.round == 2
    assert match.phase == RoundPhase.BUY
    # 攻方：800 + 勝利 3000 + 5 擊殺 ×200 = 4800
    assert world.players[0].economy.credits == 800 + ROUND_WIN_REWARD + 5 * KILL_REWARD
    # 守方：連敗補償 1900（且復活、血量重置、Spike 重置）
    assert world.players[5].economy.credits == 800 + 1900
    assert world.players[5].alive and world.players[5].health == 100.0
    assert world.spike.state == SpikeState.IDLE


def test_timeout_defenders_win():
    world, match = _match_world()
    for _ in range(int(30.0 / DT) + 1):
        world.step([None] * 10, DT)
    # 雙方都活著且無人安放 → 時間到守方勝
    for _ in range(int(100.0 / DT)):
        world.step([None] * 10, DT)
    assert match.phase == RoundPhase.END
    assert match.round_winner == TEAM_DEFENDERS
    assert match.round_reason == "round_timeout"


def test_loss_streak_bonus_escalates():
    world, match = _match_world()
    # 連續 3 場敗給 team1：每場讓 team0 全滅
    for r in range(3):
        for _ in range(int(30.0 / DT) + 1):
            world.step([None] * 10, DT)
        for s in range(0, 5):
            world.players[s].apply_damage(9999, source_slot=5, weapon_key="vandal")
        world.step([None] * 10, DT)
        for _ in range(int(4.0 / DT) + 1):
            world.step([None] * 10, DT)
    assert match.round == 4
    # team0 連敗第 3 場後補償應為 2900
    # 第三場結算時 loss_streak[0] == 3
    assert world.players[0].economy.credits >= 800 + 1900 + 2400 + 2900


def test_half_swap_attackers():
    world, match = _match_world()
    assert match.attackers(1) == TEAM_ATTACKERS
    assert match.attackers(13) == TEAM_DEFENDERS      # 下半場攻守互換
    assert match.attackers(25) == TEAM_ATTACKERS


# --------------------------------------------------------------------- #
# Spike（M9）
# --------------------------------------------------------------------- #
def _spike_world():
    world = World()
    spike = SpikeController(world, world.map_data)
    world.spike = spike
    return world, spike


def step(world, seconds):
    for _ in range(int(seconds / DT)):
        world.step([None] * 10, DT)


def test_plant_completes_and_rewards_attackers():
    world, spike = _spike_world()
    world.players[0].pos = Vec3(12, 0, 10)     # A 點內
    assert spike.try_begin_plant(0)
    assert spike.state == SpikeState.PLANTING
    step(world, PLANT_TIME + 0.05)
    assert spike.state == SpikeState.PLANTED
    assert spike.site.name == "A"
    # 攻方全員 +300
    assert world.players[0].economy.credits == 1100
    assert world.players[4].economy.credits == 1100
    assert world.players[5].economy.credits == 800   # 守方無


def test_plant_cancel_when_moving():
    world, spike = _spike_world()
    world.players[0].pos = Vec3(12, 0, 10)
    assert spike.try_begin_plant(0)
    world.players[0].pos = Vec3(20, 0, 10)     # 離開點位 → 中斷
    step(world, 0.1)
    assert spike.state == SpikeState.IDLE


def test_defuse_with_half_checkpoint():
    world, spike = _spike_world()
    world.players[0].pos = Vec3(12, 0, 10)
    spike.try_begin_plant(0)
    step(world, PLANT_TIME + 0.05)
    assert spike.state == SpikeState.PLANTED
    # 守方 5 號拆彈
    world.players[5].pos = Vec3(12, 0, 10)
    assert spike.try_begin_defuse(5)
    assert spike.state == SpikeState.DEFUSING
    step(world, HALF_DEFUSE_CHECKPOINT + 0.05)
    spike.set_hold_defuse(5, False)            # 過半後中斷 → 保留進度
    assert spike.state == SpikeState.PLANTED
    assert spike.defuse_progress >= HALF_DEFUSE_CHECKPOINT
    assert spike.try_begin_defuse(5)           # 續拆
    step(world, HALF_DEFUSE_CHECKPOINT + 0.05)
    assert spike.state == SpikeState.DEFUSED


def test_detonation_kills_defenders():
    world, spike = _spike_world()
    world.players[0].pos = Vec3(12, 0, 10)
    spike.try_begin_plant(0)
    step(world, PLANT_TIME + 0.05)
    world.players[5].pos = Vec3(12, 0, 10)     # 守方在爆炸範圍
    world.players[6].pos = Vec3(50, 0, 50)     # 太遠
    step(world, FUSE_TIME + 0.05)
    assert spike.state == SpikeState.DETONATED
    assert not world.players[5].alive
    assert world.players[6].alive
    assert world.players[6].health == 100.0
