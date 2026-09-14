"""工具鏈：VFX 粒子 / SVG / 擊殺特效 / 事件綁定測試。"""

import xml.etree.ElementTree as ET

import pytest

from tools.fx.events import EVENT_FX, all_events, fx_for, validate_bindings
from tools.fx.killfeed import (
    KillEntry,
    kill_confirm_sequence,
    kill_feed_entry,
    multi_kill_label,
    multi_kill_thresholds,
)
from tools.sfx import synth
from tools.vfx import particles, svg


# --------------------------------------------------------------------- #
# 粒子
# --------------------------------------------------------------------- #
def test_preset_exists():
    for name in ("muzzle_flash", "explosion_debris", "smoke_puff", "blood",
                 "shell_casing", "spark", "kill_confirm", "hit_marker", "tracer"):
        assert particles.preset(name).name == name
    with pytest.raises(KeyError):
        particles.preset("nope")


def test_animate_frames_deterministic():
    a = particles.animate_frames(particles.preset("explosion_debris"), seed=3)
    b = particles.animate_frames(particles.preset("explosion_debris"), seed=3)
    assert a == b


def test_animate_frames_progression():
    frames = particles.animate_frames(particles.preset("spark"), seed=1)
    assert len(frames) > 5
    # 重力使粒子下降：最後一幀的平均 y 低於第一幀
    y_first = sum(p["pos"][1] for p in frames[0]["particles"]) / max(1, len(frames[0]["particles"]))
    y_last = sum(p["pos"][1] for p in frames[-1]["particles"]) / max(1, len(frames[-1]["particles"]))
    assert y_last < y_first


def test_emitter_to_dict_jsonable():
    d = particles.to_dict(particles.preset("muzzle_flash"))
    assert d["kind"] == "cone"
    assert len(d["color_start"]) == 3


# --------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------- #
def test_svg_generates_parseable_xml():
    for name, fn in svg.VFX_SVG_REGISTRY.items():
        content = fn({})
        root = ET.fromstring(content)            # 必須是合法 XML
        assert root.tag.endswith("svg")          # 含 SVG 命名空間前綴
        assert "width" in root.attrib


def test_svg_registry_complete():
    for required in ("hud_crosshair", "hud_kill_confirm", "sprite_explosion",
                     "sprite_smoke", "hud_icon_spike"):
        assert required in svg.VFX_SVG_REGISTRY


# --------------------------------------------------------------------- #
# 擊殺特效
# --------------------------------------------------------------------- #
def test_kill_feed_entry():
    e = KillEntry(killer="A", victim="B", weapon="vandal", headshot=True, streak=2)
    fx = kill_feed_entry(e)
    assert fx["feed"]["headshot"] is True
    assert fx["feed"]["streak"] == 2
    assert fx["sfx"] == "headshot_confirm"
    assert fx["announce"] == "Double Kill"


def test_kill_confirm_frames_animate():
    frames = kill_confirm_sequence(streak=3)
    assert frames[0]["alpha"] < 0.5               # 淡入
    assert frames[0]["scale"] < 1.0               # 縮放
    assert any(f["alpha"] == 1.0 for f in frames) # 完全顯示
    assert frames[-1]["alpha"] < 1.0              # 淡出


def test_multi_kill_labels():
    assert multi_kill_label(1) is None
    assert multi_kill_label(2) == "Double Kill"
    assert multi_kill_label(5) == "ACE!"
    assert len(multi_kill_thresholds()) >= 4


# --------------------------------------------------------------------- #
# 事件綁定
# --------------------------------------------------------------------- #
def test_event_bindings_cover_game_events():
    for ev in ("kill", "headshot", "damage_taken", "reload", "ability_cast",
               "flash_explode", "smoke_spawn", "trap_trigger", "spike_planted",
               "spike_defused", "spike_detonated", "round_win", "round_loss",
               "buy_success", "buy_failed"):
        assert fx_for(ev) is not None, ev


def test_all_bindings_valid():
    issues = validate_bindings(set(synth.SFX_REGISTRY),
                               set(particles.PRESETS) | set(svg.VFX_SVG_REGISTRY))
    assert issues == [], issues


def test_unknown_event_returns_none():
    assert fx_for("no_such_event") is None
