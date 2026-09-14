"""工具鏈：槍械模組化 + 武器產生器測試。"""

import math

import pytest

from server.game.entities import World
from server.game.weapons import weapon
from tools.weapons.generator import FRAME_KEYS, generate_batch, generate_weapon, validate_balance
from tools.weapons.modular import MOD_POOL, Mod, ModdableWeapon, frame_from_weapon


def test_mod_validation_rejects_bad_slot_and_stat():
    with pytest.raises(ValueError):
        Mod("bad", "壞槽位", "body", 100, {"damage_mult": 1.1})     # 槽位不存在
    with pytest.raises(ValueError):
        Mod("bad2", "壞統計", "barrel", 100, {"teleport": 1.0})     # 統計不存在


def test_install_respects_slots():
    frame = frame_from_weapon("vandal")
    mw = ModdableWeapon(frame)
    assert mw.install("barrel", MOD_POOL["barrel"][0])              # 相容
    assert not mw.install("sight", MOD_POOL["barrel"][0])           # 槽位不符


def test_mod_effects_math():
    frame = frame_from_weapon("vandal")                             # 40 dmg, 25 mag
    mw = ModdableWeapon(frame)
    mw.install("barrel", MOD_POOL["barrel"][0])                     # dmg ×1.08, spread ×0.9
    mw.install("mag", MOD_POOL["mag"][0])                           # mag +10, reload ×1.15
    s = mw.stats()
    assert math.isclose(s.damage, 40 * 1.08, rel_tol=1e-9)
    assert s.mag_size == 35
    assert math.isclose(s.reload_time, 2.5 * 1.15, rel_tol=1e-9)
    # 底層武器庫仍不受影響
    assert weapon("vandal").damage == 40
    assert weapon("vandal").mag_size == 25


def test_uninstall():
    frame = frame_from_weapon("phantom")
    mw = ModdableWeapon(frame)
    mw.install("sight", MOD_POOL["sight"][0])
    assert mw.uninstall("sight") is not None
    assert mw.mods == {}


def test_generate_weapon_deterministic():
    a = generate_weapon(seed=7, frame_key="vandal")
    b = generate_weapon(seed=7, frame_key="vandal")
    assert a.summary() == b.summary()
    assert a.stats().key == b.stats().key


def test_generate_batch_covers_frames():
    batch = generate_batch(seed=100, count=8)
    assert len(batch) == 8
    keys = {mw.frame.key for mw in batch}
    assert len(keys) >= 4


def test_balance_validation():
    # 正常生成的武器應通過平衡驗證
    for seed in range(20):
        mw = generate_weapon(seed=seed)
        assert validate_balance(mw.stats()) == [], f"seed={seed}"
    # 故意失衡（超強傷害）應被偵測
    frame = frame_from_weapon("vandal")
    mw = ModdableWeapon(frame)
    mw.install("barrel", Mod("x", "超重管", "barrel", 1, {"damage_mult": 5.0}))
    assert validate_balance(mw.stats()) != []


def test_modded_weapon_usable_in_game():
    """產生的武器能真正進遊戲：裝上、射擊、造成傷害。"""
    world = World()
    for i, p in enumerate(world.players):
        if i not in (0, 1):
            p.alive = False
    world.players[0].pos = __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 4)   # 開闊處
    world.players[1].pos = __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 8)
    mw = generate_weapon(seed=5, frame_key="vandal")
    stats = mw.stats()
    world.players[0].weapon = __import__("server.game.entities", fromlist=["WeaponState"]).WeaponState(stats, world.rng)
    assert world.players[0].weapon.stats.damage >= 40 * 0.96       # 模組化後仍正常
    # 射一發 → 擊中
    import math as m
    eye = world.players[0].pos + __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 1.6, 0)
    tgt = world.players[1].pos + __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 1.0, 0)
    aim = (tgt - eye).normalized()
    hits = world.fire_shot(0, m.degrees(m.atan2(aim.x, aim.z)), m.degrees(m.asin(aim.y)))
    assert len(hits) == 1
    assert world.players[1].health < 100.0
