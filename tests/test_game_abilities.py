"""M10-M13/M15：狀態干擾、技能原型、投擲物、煙霧、部署物測試。"""

import random

import pytest

from server.core.math_core import Vec3, dir_from_yaw_pitch
from server.game.abilities import (
    AGENTS,
    DeployableAbility,
    FlashAbility,
    FragAbility,
    SmokeAbility,
)
from server.game.entities import World
from server.game.status import BLIND, CONCUSS, VULNERABLE, StatusEffectSystem

DT = 1.0 / 128.0


def step(world, seconds):
    for _ in range(int(seconds / DT)):
        world.step([None] * 10, DT)


# --------------------------------------------------------------------- #
# M13 狀態干擾
# --------------------------------------------------------------------- #
def test_status_effects_basics():
    s = StatusEffectSystem()
    assert s.can_shoot
    s.apply(BLIND, 2.0)
    assert not s.can_shoot
    assert s.sight_blocked
    s.update(3.0)
    assert s.can_shoot                      # 過期


def test_status_stacking_takes_longest():
    s = StatusEffectSystem()
    s.apply(VULNERABLE, 1.0, 0.5)
    s.apply(VULNERABLE, 5.0, 1.0)           # 更久 + 更強
    assert s.damage_taken_mult == 2.0
    s.update(2.0)                           # 只剩 3s 的
    assert s.has(VULNERABLE)


def test_concuss_slows():
    s = StatusEffectSystem()
    s.apply(CONCUSS, 2.0)
    assert s.move_speed_mult == 0.65
    s.update(2.1)
    assert s.move_speed_mult == 1.0


def test_vulnerable_increases_damage():
    world = World()
    p = world.players[1]
    p.status.apply(VULNERABLE, 3.0, 0.5)
    before = p.health
    p.apply_damage(40)
    assert before - p.health == 60.0        # 40 × 1.5


def test_render_state_output():
    s = StatusEffectSystem()
    s.apply(BLIND, 1.0)
    out = s.render_state()
    assert out[0]["kind"] == "blind"
    assert out[0]["time_left"] > 0.0


# --------------------------------------------------------------------- #
# M10-M12 技能原型
# --------------------------------------------------------------------- #
def test_flash_blinds_enemies():
    world = World()
    world.players[0].pos = Vec3(0, 0, 4)     # Courtyard（避開中央柱）
    world.players[5].pos = Vec3(1.5, 0, 8)   # 敵方在 MidTop 開闊帶
    flash = FlashAbility()
    flash.cast(world, 0, dir_from_yaw_pitch(0, 0))
    assert len(world.projectiles) == 1
    # 推進到爆炸（落地即爆 / fuse 1.2s）
    step(world, 1.5)
    assert world.players[5].status.has("blind")
    assert not world.players[0].status.has("blind")     # 隊友不受影響


def test_frag_damages_enemies():
    world = World()
    world.players[0].pos = Vec3(0, 0, 4)     # Courtyard（避開中央柱）
    world.players[5].pos = Vec3(1.5, 0, 8)   # 敵方在 MidTop 開闊帶
    frag = FragAbility()
    frag.cast(world, 0, dir_from_yaw_pitch(0, 0))
    step(world, 2.0)
    assert world.players[5].health < 100.0
    assert len(world.projectiles) == 0       # 已消耗


def test_smoke_blocks_los_and_expires():
    world = World()
    world.players[0].pos = Vec3(0, 0, 0)
    smoke = SmokeAbility()
    smoke.cast(world, 0, dir_from_yaw_pitch(0, 0))    # 向前投擲
    step(world, 1.5)
    assert len(world.smokes) == 1
    s = world.smokes[0]
    assert s.active
    # 視線被煙霧擋住
    assert s.blocks_segment(Vec3(0, 1, 0), Vec3(0, 1, 30))
    # 持續時間結束
    step(world, 16.0)
    assert world.smokes == []


def test_trap_trigger_on_enemy():
    world = World()
    world.players[0].pos = Vec3(3, 0, 0)     # Courtyard 東側（避開中央柱）
    trap = DeployableAbility()
    trap.cast(world, 0, dir_from_yaw_pitch(0, 0))
    assert len(world.deployables) == 1
    # 敵方（team1）走進觸發半徑
    world.players[5].pos = Vec3(3, 0, 2.5)
    step(world, 0.5)
    assert world.players[5].health < 100.0
    assert world.players[5].status.has("concuss")
    assert world.deployables == []           # 單次觸發已消耗


def test_ability_system_charges_and_cooldown():
    from server.game.abilities import AbilitySystem

    sys = AbilitySystem([FlashAbility(), FragAbility()])
    world = World()
    assert sys.cast(0, world, 0, Vec3(0, 0, 1))
    assert not sys.cast(0, world, 0, Vec3(0, 0, 1))   # 已用光且冷卻
    sys.update(25.0)                                  # 等冷卻完但無充能
    assert not sys.cast(0, world, 0, Vec3(0, 0, 1))   # 充能耗盡
    assert sys.slots[0].charges_left == 0
    assert sys.cast(1, world, 0, Vec3(0, 0, 1))       # 第二招可用


# --------------------------------------------------------------------- #
# M15 Agent 原型
# --------------------------------------------------------------------- #
def test_agent_kits_exist():
    # 10 名特務 + 4 個原型
    expected = {
        "jett", "yoru", "neon", "sova", "breach", "kayo",
        "omen", "brimstone", "viper", "sage",
        "assault", "sentinel", "duelist", "controller",
    }
    assert set(AGENTS) == expected
    for key, (name, abilities) in AGENTS.items():
        assert name
        # 特務有 4 個技能，原型有 2-3 個
        assert len(abilities) >= 2
        assert all(a.name for a in abilities)
        assert all(a.charges >= 1 for a in abilities)


def test_agent_assignment():
    world = World()
    assert world.players[0].agent_key == "assault"
    assert len(world.players[0].abilities.slots) == 4   # flash/frag/smoke/stim (補滿到 4)
    world.players[0].abilities.slots[0].charges_left = 1
    assert world.players[0].abilities.slots[0].charges_left == 1
