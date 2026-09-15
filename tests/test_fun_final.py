"""tests/test_fun_final.py — Final system integration test"""
import json
import os

import pytest


# ── Shop tests ───────────────────────────────────────────────────────────────
def test_shop_night_market():
    from server.game.shop import ALL_SKINS, generate_night_market
    nm = generate_night_market(1, "2026-09-16")
    assert len(nm) == 6
    for item in nm:
        assert "skin_id" in item
        assert "discount_pct" in item
        assert 0 < item["discount_pct"] < 100
        assert item["sale_vp"] <= item["original_vp"]


def test_shop_daily():
    from server.game.shop import generate_daily_shop
    ds = generate_daily_shop("2026-09-16")
    assert len(ds) == 4
    for item in ds:
        assert "skin_id" in item
        assert "price_vp" in item
        assert item["price_vp"] > 0


def test_shop_purchase():
    from server.game.shop import PlayerShopState
    shop = PlayerShopState(vp=500)
    assert shop.purchase("vandal_0", 10) is True
    assert "vandal_0" in shop.owned_skins
    assert shop.vp == 490
    assert shop.equip("vandal", "vandal_0") is True
    assert shop.equipped["vandal"] == "vandal_0"
    assert shop.purchase("vandal_0", 10) is False  # already owned
    assert shop.vp == 490


# ── Party tests ──────────────────────────────────────────────────────────────
def test_party_create_join_leave():
    from server.game.party import PartyManager
    pm = PartyManager()
    party = pm.create(0, "Alice")
    assert party.host_slot == 0
    assert len(party.members) == 1
    assert party.invite_code != ""
    joined = pm.join(party.invite_code, 1, "Bob")
    assert joined is not None
    assert len(party.members) == 2
    pm.leave(1)
    assert len(party.members) == 1
    pm.leave(0)
    assert len(pm.parties) == 0


def test_party_ready_and_queue():
    from server.game.party import PartyManager
    pm = PartyManager()
    party = pm.create(0, "P1")
    for i in range(1, 5):
        pm.join(party.invite_code, i, f"P{i+1}")
    assert len(party.members) == 5
    assert pm.all_ready(party.id) is False
    for i in range(5):
        pm.ready(i, True)
    assert pm.all_ready(party.id) is True
    assert pm.queue(party.id) is True


# ── History tests ────────────────────────────────────────────────────────────
def test_history_add_retrieve():
    from server.game.history import HistoryRecord, MatchHistory
    mh = MatchHistory(max_records=10)
    for i in range(12):
        mh.add(HistoryRecord(
            match_id=f"m{i}", mode="competitive", date="2026-09-16",
            won=(i % 2 == 0), score_atk=13, score_def=i % 13,
            kills=10 + i, deaths=5, assists=3, agent="jett", map_name="bind",
            rr_change=10 if i % 2 == 0 else -10,
        ))
    assert len(mh.records) == 10
    latest = mh.get(1)
    assert latest[0].match_id == "m11"


# ── Practice tests ───────────────────────────────────────────────────────────
def test_practice_bots():
    from server.game.practice import PracticeRange
    pr = PracticeRange()
    pr.spawn_bots(10)
    assert len(pr.bots) == 10
    assert pr.round_active is True
    for bot in pr.bots[:5]:
        pr.hit_bot(bot.slot, 50.0)
    assert pr.stats.kills >= 0
    for bot in pr.bots:
        if bot.alive:
            pr.hit_bot(bot.slot, 200.0)
    assert pr.stats.kills == 10


def test_practice_accuracy():
    from server.game.practice import PracticeRange
    pr = PracticeRange()
    pr.spawn_bots(5)
    pr.record_shot()
    pr.record_shot()
    pr.hit_bot(0, 100.0)
    pr.hit_bot(1, 100.0)
    assert pr.stats.shots == 4
    assert pr.stats.hits == 2
    assert pr.stats.accuracy == 50.0


# ── Map loading tests ────────────────────────────────────────────────────────
def test_bind_map_exists():
    map_path = os.path.join(
        os.path.dirname(__file__), "..", "client", "assets", "maps", "bind.json"
    )
    assert os.path.exists(map_path), f"bind.json not found at {map_path}"
    with open(map_path) as f:
        data = json.load(f)
    assert "walls" in data
    assert len(data["walls"]) >= 50
    assert "sites" in data
    assert len(data["sites"]) == 2
    assert data["sites"][0]["name"] == "A"
    assert data["sites"][1]["name"] == "B"
    assert "spawns_attackers" in data
    assert len(data["spawns_attackers"]) == 5
    assert "spawns_defenders" in data
    assert len(data["spawns_defenders"]) == 5
    assert "buy_zone_attackers" in data
    assert "buy_zone_defenders" in data
    assert "teleporters" in data
    assert len(data["teleporters"]) == 2
    for t in data["teleporters"]:
        assert "entrance" in t
        assert "exit" in t
        assert "cooldown" in t
        assert t["cooldown"] == 10.0
        assert "name" in t


# ── Settings tests ───────────────────────────────────────────────────────────
def test_settings_vars_exist():
    gd_path = os.path.join(
        os.path.dirname(__file__), "..", "client", "scripts", "vanta_global.gd"
    )
    assert os.path.exists(gd_path), "vanta_global.gd not found"
    with open(gd_path, encoding="utf-8") as f:
        content = f.read()
    for var_name in [
        "colorblind_mode", "font_size_index", "subtitles_on",
        "master_volume", "sfx_volume", "bgm_volume", "graphics_quality",
    ]:
        assert var_name in content, f"Missing variable: {var_name}"


# ── Agents tests ─────────────────────────────────────────────────────────────
def test_enhanced_abilities_exist():
    from server.game import abilities as ab
    enhanced_names = [
        "enhanced_jett_cloudburst", "enhanced_jett_tailwind", "enhanced_jett_blade_storm",
        "enhanced_sage_slow_orb", "enhanced_sage_barrier_orb", "enhanced_sage_healing_orb",
        "enhanced_sage_resurrection",
        "enhanced_brim_stim_beacon", "enhanced_brim_incendiary", "enhanced_brim_sky_smoke",
        "enhanced_brim_orbital_strike",
        "enhanced_viper_toxic_screen", "enhanced_viper_pit",
        "enhanced_sova_recon_bolt", "enhanced_sova_hunter_fury",
        "enhanced_omen_teleport",
        "enhanced_breach_fault_line",
        "enhanced_neon_sprint",
    ]
    for name in enhanced_names:
        assert hasattr(ab, name), f"Missing: {name}"


def test_8_agents_have_4_abilities():
    from server.game.abilities import AGENTS
    core_agents = ["jett", "yoru", "neon", "sova", "breach", "kayo", "omen", "brimstone", "viper", "sage"]
    for key in core_agents:
        assert key in AGENTS, f"Agent '{key}' not in AGENTS"
        name, abilities = AGENTS[key]
        assert len(abilities) >= 4, f"Agent '{key}' has only {len(abilities)} abilities"
