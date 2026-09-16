"""工具鏈：人物（角色）產生器測試。"""

import xml.etree.ElementTree as ET

import pytest

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.status import SPEED_BOOST
from tools.agents.generator import (
    ROLES,
    generate_agent,
    generate_batch,
    register_agent,
    validate_agent,
)
from tools.agents.portrait import portrait_svg


# --------------------------------------------------------------------- #
# 產生器
# --------------------------------------------------------------------- #
def test_generate_deterministic():
    a = generate_agent(seed=7).to_dict()
    b = generate_agent(seed=7).to_dict()
    assert a == b


def test_different_seeds_differ():
    a = generate_agent(seed=1).to_dict()
    b = generate_agent(seed=2).to_dict()
    assert a != b


def test_all_agents_valid():
    for seed in range(1, 25):
        d = generate_agent(seed=seed).to_dict()
        assert validate_agent(d) == [], f"seed={seed}: {validate_agent(d)}"


def test_batch_unique_codenames():
    batch = generate_batch(seed=100, count=20)
    codenames = [a.codename for a in batch]
    assert len(set(codenames)) == len(codenames)     # 代號唯一
    keys = [a.key for a in batch]
    assert len(set(keys)) == len(keys)


def test_batch_covers_roles():
    batch = generate_batch(seed=100, count=24)
    roles = {a.role for a in batch}
    assert set(ROLES) <= roles                        # 四種定位都會出現


def test_validate_catches_bad_kit():
    d = generate_agent(seed=3).to_dict()
    d["kit"] = ["flash", "nope_ability"]
    assert validate_agent(d) != []


def test_validate_catches_bad_role_and_missing():
    d = generate_agent(seed=3).to_dict()
    d["role"] = "mage"
    assert validate_agent(d) != []
    del d["bio"]
    assert validate_agent(d) != []


def test_kit_contains_known_abilities():
    """四槽契約：C/Q/E 取自基礎池，X 必須是終點球池的成員（可被充能門控）。"""
    from tools.agents.generator import ULT_POOL

    basics = ("flash", "frag", "smoke", "trap", "stim", "heal")
    for seed in range(1, 20):
        a = generate_agent(seed=seed)
        assert len(a.kit) == 4, f"seed {seed}: {a.kit}"
        assert all(name in basics for name in a.kit[:3])
        assert a.kit[3] in ULT_POOL and a.ult == a.kit[3]
        assert 6 <= a.ult_cost <= 9


def test_exported_dict_carries_slots_and_ultimate():
    """匯出的 JSON 要帶 slots/ultimate——客戶端技能條與兵工廠看的是這個。"""
    from tools.agents.generator import ULT_POOL

    d = generate_agent(seed=11).to_dict()
    assert d["slots"] == ["C", "Q", "E", "X"]
    assert d["ultimate"]["key"] in ULT_POOL
    assert d["ultimate"]["cost"] == ULT_POOL[d["ultimate"]["key"]]["cost"]
    assert validate_agent(d) == []
    # 缺終點球／槽位不對的資料要擋下來
    d2 = generate_agent(seed=12).to_dict()
    d2["kit"] = d2["kit"][:3]
    assert validate_agent(d2) != []
    d3 = generate_agent(seed=13).to_dict()
    d3["ultimate"]["cost"] = 0
    assert validate_agent(d3) != []


# --------------------------------------------------------------------- #
# 肖像
# --------------------------------------------------------------------- #
def test_portrait_valid_xml():
    a = generate_agent(seed=5)
    root = ET.fromstring(portrait_svg(a))
    assert root.tag.endswith("svg")
    assert "width" in root.attrib and "height" in root.attrib


def test_portrait_deterministic():
    a = generate_agent(seed=9)
    b = generate_agent(seed=9)
    assert portrait_svg(a) == portrait_svg(b)


def test_portrait_depends_on_agent():
    a = generate_agent(seed=9)
    b = generate_agent(seed=10)
    assert portrait_svg(a) != portrait_svg(b)


def test_portrait_contains_identity():
    a = generate_agent(seed=5)
    svg = portrait_svg(a)
    assert a.codename in svg
    assert a.faction in svg
    # 定位圖騰存在
    glyph = a.stats["role_glyph"]
    assert glyph in ("flash", "smoke", "trap", "spark")


def test_portrait_accepts_dict():
    a = generate_agent(seed=5).to_dict()
    assert portrait_svg(a).startswith("<?xml")


# --------------------------------------------------------------------- #
# 遊戲整合
# --------------------------------------------------------------------- #
def test_register_and_play_agent():
    a = generate_agent(seed=11, role="duelist")
    key = register_agent(a)
    world = World()
    # 給 slot0 換上產生角色
    from server.game.entities import Player

    p = world.players[0]
    p.agent_key = key
    p.abilities = __import__("server.game.abilities", fromlist=["AbilitySystem"]).AbilitySystem(
        list(__import__("server.game.abilities", fromlist=["lookup_agent"]).lookup_agent(key)[1])
    )
    # 施放第一招（flash/stim/frag）→ 應成功
    assert p.abilities.cast(0, world, 0, __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 1))
    assert p.abilities.slots[0].charges_left == 0


def test_stim_boosts_speed():
    world = World()
    p = world.players[0]
    p.status.apply(SPEED_BOOST, 6.0, 1.0)
    assert p.status.move_speed_mult == 1.25


def test_stim_concuss_stack():
    world = World()
    p = world.players[0]
    p.status.apply(SPEED_BOOST, 6.0, 1.0)
    from server.game.status import CONCUSS

    p.status.apply(CONCUSS, 2.0)
    assert p.status.move_speed_mult == 0.65 * 1.25


def test_stim_ability_in_game_speeds_up_movement():
    """刺激技能：施放後 1 秒移動距離 > 未施放。"""
    from server.game.abilities import StimAbility

    DT = 1 / 128.0
    world = World()
    world.start_match()
    world.match.phase = __import__("server.game.match", fromlist=["RoundPhase"]).RoundPhase.ACTION
    p = world.players[0]
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    # 對照組
    for _ in range(128):
        world.step(inp, DT)
    base_dist = world.players[0].pos.z
    # 重置並施放刺激
    world.players[0].pos = __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, -12)
    StimAbility().cast(world, 0, __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 1))
    for _ in range(128):
        world.step(inp, DT)
    stim_dist = world.players[0].pos.z
    assert stim_dist > base_dist + 0.3      # 刺激明顯更快


def test_heal_ability_restores_health():
    from server.game.abilities import HealAbility

    world = World()
    p = world.players[0]
    p.apply_damage(60)
    assert p.health == 40.0
    HealAbility().cast(world, 0, __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 1))
    assert p.health == 90.0
    # 不超過上限
    HealAbility().cast(world, 0, __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 1))
    assert p.health == 100.0


def test_every_role_kit_castable():
    """每個定位的每個技能組合都能在遊戲中施放（不崩潰）。"""
    from server.core.math_core import Vec3

    for role in ROLES:
        for kit in ROLES[role]["kits"]:
            a = generate_agent(seed=role.__len__() * 3 + 1, role=role)
            a.kit = list(kit)
            key = register_agent(a)
            world = World()
            p = world.players[0]
            from server.game.abilities import AbilitySystem, lookup_agent

            p.abilities = AbilitySystem(list(lookup_agent(key)[1]))
            for idx in range(len(kit)):
                ok = p.abilities.cast(idx, world, 0, Vec3(0, 0, 1))
                assert ok, f"{role}/{kit}/{idx}"
