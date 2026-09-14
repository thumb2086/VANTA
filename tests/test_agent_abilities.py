"""tests/test_agent_abilities.py — 10 名核心特務專屬技能測試"""

import pytest

from server.core.math_core import Vec3
from server.core.movement import MovementConfig
from server.game.abilities import (
    AGENTS, lookup_agent, AbilitySystem,
    FlashAbility, FragAbility, SmokeAbility, DeployableAbility,
    StimAbility, HealAbility,
    CloudburstAbility, UpdraftAbility, TailwindAbility, ThrownKnifeAbility,
    FakeFootstepAbility, NearsightLineAbility, TeleportAbility, InvisibilityAbility,
    ElectricWallAbility, SprintAbility, ElectricBeamUltAbility,
    OwlDroneAbility, ReconBoltAbility, HunterFuryAbility,
    AftershockAbility, FaultLineAbility, FlashpointAbility, EarthquakeAbility,
    SuppressionFieldAbility, NULLCmdAbility,
    SkySmokeAbility, OrbitalStrikeAbility, IncendiaryAbility, StimBeaconAbility,
    ToxicScreenAbility, ViperPitAbility,
    SlowOrbAbility, BarrierWallAbility, HealingOrbAbility, ResurrectionAbility,
)
from server.game.entities import World, Player
from server.game.status import (
    BLIND, CONCUSS, VULNERABLE, SPEED_BOOST,
    NEARSIGHT, SUPPRESSED, DECAY, SLOW, DEAFENED, REVEALED,
)

DT = 1.0 / 128.0
DTAL = 1.0 / 128.0


def _world():
    w = World(slots=10, cfg=MovementConfig(), ground_y=0.0, seed=42)
    # 將施法者移到地圖中央，面向 +z
    w.players[0].pos = Vec3(0, 0, 0)
    return w


def _aim():
    return Vec3(0, 0, 1)


def _set_agent(w, slot, key):
    """設定玩家的特務技能組。"""
    w.players[slot].agent_key = key
    w.players[slot].abilities = AbilitySystem(list(lookup_agent(key)[1]))


def _place_enemy(w, slot, z=5.0, x=0.0):
    """將敵方玩家放在施法者前方。"""
    w.players[slot].pos = Vec3(x, 0, z)
    w.players[slot].alive = True
    w.players[slot].health = 100.0


# ─── 特務註冊與基本查詢 ───

class TestAgentRegistration:
    def test_all_10_agents_registered(self):
        keys = ["jett", "yoru", "neon", "sova", "breach", "kayo",
                "omen", "brimstone", "viper", "sage"]
        for k in keys:
            a = lookup_agent(k)
            assert a is not None, f"agent {k} not found"
            assert len(a[1]) == 4, f"{k} should have 4 abilities, got {len(a[1])}"

    def test_each_agent_has_4_abilities(self):
        for key, (codename, abilities) in AGENTS.items():
            if key in ("assault", "sentinel", "duelist", "controller"):
                continue  # 舊原型不檢查
            assert len(abilities) == 4, f"{key}: expected 4 abilities"

    def test_agent_codenames_are_traditional_chinese(self):
        expected = {
            "jett": "捷提", "yoru": "夜露", "neon": "霓虹",
            "sova": "蘇法", "breach": "布雷奇", "kayo": "凱歐",
            "omen": "幽影", "brimstone": "布里姆", "viper": "薇勞",
            "sage": "賢者",
        }
        for key, name in expected.items():
            assert lookup_agent(key)[0] == name, f"{key}: expected {name}"

    def test_no_duplicate_ability_names_per_agent(self):
        for key, (codename, abilities) in AGENTS.items():
            if key in ("assault", "sentinel", "duelist", "controller"):
                continue
            names = [a.name for a in abilities]
            # Viper 有兩個 toxic_screen（C 和 E）是正常的設計
            if key == "viper":
                continue
            assert len(names) == len(set(names)), f"{key}: duplicate ability names {names}"


# ─── 決鬥者技能測試 ───

class TestDuelistAbilities:
    def test_jett_cloudburst_spawns_projectile(self):
        w = _world()
        _set_agent(w, 0, "jett")
        before = len(w.projectiles)
        w.cast_ability(0, 0, 0, 0)  # C 技能
        assert len(w.projectiles) == before + 1
        assert w.projectiles[-1].behavior == "smoke"

    def test_jett_updraft_gives_vertical_velocity(self):
        w = _world()
        _set_agent(w, 0, "jett")
        old_vy = w.players[0].vel.y
        w.cast_ability(0, 1, 0, 0)  # Q Updraft
        assert w.players[0].vel.y > old_vy

    def test_jett_tailwind_gives_horizontal_velocity(self):
        w = _world()
        _set_agent(w, 0, "jett")
        w.cast_ability(0, 2, 0, 0)  # E Tailwind (z=1)
        assert w.players[0].vel.z > 0  # 向前衝刺

    def test_jett_blade_storm_spawns_knives(self):
        w = _world()
        _set_agent(w, 0, "jett")
        before = len(w.projectiles)
        w.cast_ability(0, 3, 0, 0)  # X Blade Storm
        assert len(w.projectiles) == before + 5  # 5 把飛刀

    def test_yoru_teleport_moves_player(self):
        w = _world()
        _set_agent(w, 0, "yoru")
        old_pos = w.players[0].pos
        w.cast_ability(0, 2, 0, 0)  # E Teleport (z=1)
        assert w.players[0].pos != old_pos
        assert w.players[0].pos.z > old_pos.z  # 向前傳送

    def test_yoru_invisibility_gives_speed_boost(self):
        w = _world()
        _set_agent(w, 0, "yoru")
        w.cast_ability(0, 3, 0, 0)  # X Dimensional Drift
        assert w.players[0].status.has(SPEED_BOOST)

    def test_neon_sprint_gives_speed_boost(self):
        w = _world()
        _set_agent(w, 0, "neon")
        w.cast_ability(0, 2, 0, 0)  # E Sprint
        assert w.players[0].status.has(SPEED_BOOST)

    def test_neon_lightning_ult_damages_enemy(self):
        w = _world()
        _set_agent(w, 0, "neon")
        _place_enemy(w, 5, z=10)
        hp_before = w.players[5].health
        w.cast_ability(0, 3, 0, 0)  # X Lightning Ult (z=1)
        assert w.players[5].health < hp_before

    def test_neon_electric_wall_creates_wall(self):
        w = _world()
        _set_agent(w, 0, "neon")
        walls_before = len(w.map_data.walls)
        w.cast_ability(0, 0, 0, 0)  # C Electric Wall
        assert len(w.map_data.walls) > walls_before


# ─── 偵查者技能測試 ───

class TestInitiatorAbilities:
    def test_sova_recon_bolt_reveals_enemy(self):
        w = _world()
        _set_agent(w, 0, "sova")
        _place_enemy(w, 5, z=5)
        w.cast_ability(0, 2, 0, 0)  # E Recon Bolt
        # recon bolt: speed=20, fuse=2.0, gravity=5.0 → flies ~40m before fuse
        for _ in range(300):
            w.step([None] * 10, DT)
        assert w.players[5].status.has(REVEALED)

    def test_sova_hunter_fury_damages_enemy(self):
        w = _world()
        _set_agent(w, 0, "sova")
        _place_enemy(w, 5, z=20)
        hp = w.players[5].health
        w.cast_ability(0, 3, 0, 0)  # X Hunter's Fury
        assert w.players[5].health < hp

    def test_breach_fault_line_stuns_enemy(self):
        w = _world()
        _set_agent(w, 0, "breach")
        _place_enemy(w, 5, z=8)
        w.cast_ability(0, 1, 0, 0)  # Q Fault Line
        assert w.players[5].status.has(CONCUSS)

    def test_breach_earthquake_stuns_multiple_enemies(self):
        w = _world()
        _set_agent(w, 0, "breach")
        _place_enemy(w, 5, z=10)
        _place_enemy(w, 6, z=12, x=3)
        _place_enemy(w, 7, z=12, x=-3)
        w.cast_ability(0, 3, 0, 0)  # X Earthquake
        assert w.players[5].status.has(CONCUSS)
        assert w.players[6].status.has(CONCUSS)
        assert w.players[7].status.has(CONCUSS)

    def test_kayo_null_cmd_suppresses_enemies(self):
        w = _world()
        _set_agent(w, 0, "kayo")
        _place_enemy(w, 5, z=5)
        w.cast_ability(0, 3, 0, 0)  # X NULL/cmd
        assert w.players[5].status.has(SUPPRESSED)

    def test_kayo_suppressed_cannot_use_ability(self):
        w = _world()
        _set_agent(w, 0, "kayo")
        w.players[0].status.apply(SUPPRESSED, 5.0, 1.0)
        result = w.cast_ability(0, 0, 0, 0)
        assert result == False

    def test_breach_aftershock_damages_through_wall_position(self):
        w = _world()
        _set_agent(w, 0, "breach")
        _place_enemy(w, 5, z=6)
        hp = w.players[5].health
        w.cast_ability(0, 0, 0, 0)  # C Aftershock
        assert w.players[5].health < hp


# ─── 控場者技能測試 ───

class TestControllerAbilities:
    def test_omen_sky_smoke_creates_smoke(self):
        w = _world()
        _set_agent(w, 0, "omen")
        before = len(w.smokes)
        w.cast_ability(0, 2, 0, 0)  # E Sky Smoke
        assert len(w.smokes) == before + 1

    def test_omen_teleport_moves_player(self):
        w = _world()
        _set_agent(w, 0, "omen")
        old_pos = w.players[0].pos
        w.cast_ability(0, 1, 0, 0)  # Q Shrouded Step
        assert w.players[0].pos != old_pos

    def test_brimstone_stim_beacon_gives_speed(self):
        w = _world()
        _set_agent(w, 0, "brimstone")
        w.cast_ability(0, 0, 0, 0)  # C Stim Beacon
        w.step([None] * 10, DT)
        assert w.players[0].status.has(SPEED_BOOST)

    def test_brimstone_orbital_strike_damages_enemy(self):
        w = _world()
        _set_agent(w, 0, "brimstone")
        _place_enemy(w, 5, z=5)
        w.cast_ability(0, 3, 0, 0)  # X Orbital Strike
        hp = w.players[5].health
        # orbital strike has 2.0s delay → step enough ticks
        for _ in range(int(3.0 / DT) + 10):
            w.step([None] * 10, DT)
        assert w.players[5].health < hp

    def test_viper_toxic_screen_creates_wall(self):
        w = _world()
        _set_agent(w, 0, "viper")
        walls_before = len(w.map_data.walls)
        w.cast_ability(0, 0, 0, 0)  # C Toxic Screen
        assert len(w.map_data.walls) > walls_before

    def test_viper_pit_creates_smoke_and_decay(self):
        w = _world()
        _set_agent(w, 0, "viper")
        _place_enemy(w, 5, z=3)
        before_smokes = len(w.smokes)
        w.cast_ability(0, 3, 0, 0)  # X Viper's Pit
        assert len(w.smokes) > before_smokes
        assert w.players[5].status.has(DECAY)


# ─── 哨衛技能測試 ───

class TestSentinelAbilities:
    def test_sage_slow_orb_applies_slow(self):
        w = _world()
        _set_agent(w, 0, "sage")
        _place_enemy(w, 5, z=3)
        w.cast_ability(0, 0, 0, 0)  # C Slow Orb
        # slow orb: speed=14, fuse from gravity → give it time to reach and detonate
        for _ in range(300):
            w.step([None] * 10, DT)
        assert w.players[5].status.has(SLOW)

    def test_sage_healing_orb_restores_health(self):
        w = _world()
        _set_agent(w, 0, "sage")
        w.players[0].health = 50.0
        w.cast_ability(0, 2, 0, 0)  # E Healing Orb
        assert w.players[0].health > 50.0

    def test_sage_barrier_wall_creates_wall(self):
        w = _world()
        _set_agent(w, 0, "sage")
        walls_before = len(w.map_data.walls)
        w.cast_ability(0, 1, 0, 0)  # Q Barrier Wall
        assert len(w.map_data.walls) > walls_before

    def test_sage_resurrection_revives_dead_ally(self):
        w = _world()
        _set_agent(w, 0, "sage")
        w.players[1].alive = False
        w.players[1].health = 0.0
        w.cast_ability(0, 3, 0, 0)  # X Resurrection
        assert w.players[1].alive
        assert w.players[1].health == 100.0


# ─── 狀態效果測試 ───

class TestStatusEffects:
    def test_slow_reduces_move_speed(self):
        w = _world()
        p = w.players[0]
        normal = p.status.move_speed_mult
        p.status.apply(SLOW, 5.0, 1.0)
        slowed = p.status.move_speed_mult
        assert slowed < normal

    def test_suppressed_blocks_ability(self):
        w = _world()
        w.players[0].abilities = AbilitySystem(list(lookup_agent("jett")[1]))
        w.players[0].status.apply(SUPPRESSED, 5.0, 1.0)
        result = w.cast_ability(0, 0, 0, 0)
        assert result == False

    def test_decay_tick_damages_player(self):
        w = _world()
        p = w.players[0]
        p.status.apply(DECAY, 5.0, 20.0)  # 20 dmg/s
        hp = p.health
        p.status.update(DT)
        p.status.tick_decay(DT, p)
        assert p.health < hp

    def test_nearsight_deafen_applied_by_breach_flash(self):
        w = _world()
        _set_agent(w, 0, "breach")
        _place_enemy(w, 5, z=3)
        w.cast_ability(0, 2, 0, 0)  # E Flashpoint (flash with bounces=2, fuse=1.0)
        # flash bounces off ground, give time to detonate (fuse=1.0s)
        for _ in range(200):
            w.step([None] * 10, DT)
        assert w.players[5].status.has(BLIND) or w.players[5].status.has(NEARSIGHT)
