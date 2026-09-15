"""工具鏈：VFX 粒子 / SVG / 擊殺特效 / 事件綁定 / vfx2 特效庫測試。"""

import json
import pathlib

import xml.etree.ElementTree as ET

VFX_JSON = pathlib.Path(__file__).resolve().parents[1] / "tools" / "assets" / "vfx"

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


# ===================================================================== #
# vfx2：資料驅動的特效庫（blueprints / sprites / decals）
#
# 重點不是「Python 自己圓滾滾」，而是 Godot 端有沒有老實把資料用完：
# 只要有一個錨點／圖層型別／顏色鍵在 client 找不到對應實作，
# 就是「資料寫了、遊戲裡看不到」——所以這裡用原始碼比對把兩邊釘死。
# ===================================================================== #
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENT_DIR = REPO_ROOT / "client" / "scripts"
VFX2_JSON = REPO_ROOT / "tools" / "assets" / "vfx"
SKIN_FX_KEYS = {"style", "muzzle", "tracer", "impact", "kill", "smoke", "muzzle_color",
                "muzzle_scale", "muzzle_shape", "light_energy", "light_color", "tracer_color",
                "tracer_width", "tracer_style", "impact_color", "impact_style", "decal",
                "kill_color", "kill_style", "banner_frame", "shell_color", "shell_glow",
                "sound_key", "sound_pitch", "sound_gain_db", "smoke_color"}


@pytest.fixture(scope="module")
def blueprints():
    from tools.vfx.blueprints import BLUEPRINTS, validate_blueprints
    assert validate_blueprints() == []
    return BLUEPRINTS


def test_blueprints_cover_every_style_slot(blueprints):
    """每種 style 都要湊齊 shot/impact/kill 三張藍圖（缺一種就會有槍開火沒特效）。"""
    by_style: dict[str, set] = {}
    for bp in blueprints.values():
        by_style.setdefault(bp["style"], set()).add(bp["kind"])
    assert by_style, "沒有產生任何藍圖"
    for style, kinds in by_style.items():
        assert {"shot", "impact", "kill"} <= kinds, (style, kinds)
    assert any(bp["kind"] == "common" for bp in blueprints.values())


def test_blueprint_layers_are_sane(blueprints):
    from tools.vfx.blueprints import LAYER_TYPES
    for bid, bp in blueprints.items():
        assert bp["layers"], f"{bid} 沒有圖層"
        assert 0.02 <= float(bp["duration"]) <= 6.0, (bid, bp["duration"])
        assert 0 < int(bp["budget"]) <= 40, (bid, bp["budget"])
        for layer in bp["layers"]:
            assert layer["type"] in LAYER_TYPES, (bid, layer["type"])
            assert float(layer.get("delay", 0.0)) >= 0.0, (bid, layer)
            if "ttl" in layer and layer["ttl"] is not None:
                assert float(layer["ttl"]) > 0.0, (bid, layer)


def test_blueprint_references_resolve(blueprints):
    from tools.vfx.decals import DECALS
    from tools.vfx.particles import PRESETS
    for bid, bp in blueprints.items():
        for l in bp["layers"]:
            preset = l.get("preset")
            if l["type"] == "particles" and preset:
                assert preset in PRESETS, f"{bid}: 引用不存在的粒子預設 {preset}"
            if l["type"] == "decal" and preset:
                assert preset in DECALS, f"{bid}: 引用不存在的貼花 {preset}"
            # 動態取用的欄位必須是 skin.fx 裡真的存在的鍵
            for key in ("preset_key", "color_key", "scale_key", "energy_key",
                        "ttl_key", "style_key", "frame_key"):
                v = l.get(key)
                if v:
                    assert v in SKIN_FX_KEYS, f"{bid}: {key}={v} 不是合法的 skin.fx 欄位"


def test_blueprint_colors_are_hex(blueprints):
    for bid, bp in blueprints.items():
        for l in bp["layers"]:
            v = l.get("color")
            if v is not None:
                assert isinstance(v, str) and len(v) == 7 and v.startswith("#"), (bid, v)


def test_blueprint_audio_resolves(blueprints):
    """音效：要嘛直接給 SFX 鍵，要嘛走 skin 覆寫（override_key 必須是合法欄位）。"""
    from tools.sfx.synth import SFX_REGISTRY
    for bid, bp in blueprints.items():
        audio = bp.get("audio") or {}
        if "sfx" in audio:
            assert audio["sfx"] in SFX_REGISTRY, f"{bid}: 音效鍵 {audio['sfx']} 不存在"
            assert 0.4 <= float(audio.get("pitch", 1.0)) <= 2.5, (bid, audio)
        if "override_key" in audio:
            assert audio["override_key"] in SKIN_FX_KEYS, (bid, audio["override_key"])
            assert audio.get("pitch_key") in SKIN_FX_KEYS, (bid, audio)


def test_blueprint_anchors_implemented_in_client(blueprints):
    src = (CLIENT_DIR / "fx_manager.gd").read_text(encoding="utf-8")
    for at in sorted({l.get("at", "") for b in blueprints.values() for l in b["layers"]}):
        if at:
            assert f'"{at}"' in src, f"fx_manager.gd 沒有錨點 {at}"


def test_blueprint_layer_types_implemented_in_client(blueprints):
    src = (CLIENT_DIR / "fx_manager.gd").read_text(encoding="utf-8")
    for ty in sorted({l["type"] for b in blueprints.values() for l in b["layers"]}):
        assert f'"{ty}"' in src, f"fx_manager.gd 沒有圖層型別 {ty}"


def test_particles_presets_are_capped():
    from tools.vfx.particles import PRESETS, validate_presets
    assert validate_presets() == []
    for name, p in PRESETS.items():
        assert 1 <= p.count <= 220, (name, p.count)
        # 一次性特效壽命要短；loop 的（例如 lingering 煙霧）允許更長，但仍有上限
        life_max = 12.0 if p.loop else 4.0
        assert 0.02 <= p.life <= life_max, (name, p.life, p.loop)
        assert p.speed >= 0.0 and p.size > 0.0, name
        for c in (p.color_start, p.color_end):
            assert len(c) == 3 and all(0 <= v <= 255 for v in c), (name, c)
        # 有重力的預設必須真的往下掉，否則「火花往上飄」這種劣化會被靜默接受
        if p.gravity > 6.0:
            frames = [f for f in particles.animate_frames(p, seed=1) if f["particles"]]
            if len(frames) > 5:
                first = sum(q["pos"][1] for q in frames[0]["particles"]) / len(frames[0]["particles"])
                last = sum(q["pos"][1] for q in frames[-1]["particles"]) / len(frames[-1]["particles"])
                # 允許一些上浮（煙/塵會往上），但「火花一直往上飛」就是錯的
                assert last < first + p.life * 2.0, (name, round(first, 2), round(last, 2))


def test_sprites_and_decals_validate():
    from tools.vfx.decals import DECALS, validate_decals
    from tools.vfx.sprites import SPRITES, validate_sprites
    assert validate_sprites() == [] and validate_decals() == []
    assert len(SPRITES) >= 12 and len(DECALS) >= 10
    for name, sp in SPRITES.items():
        assert sp.get("size", 64) >= 16, name
    for name, dc in DECALS.items():
        assert float(dc.get("size", 0.5)) > 0.0, name


def test_mesh_primitives_are_usable():
    from tools.vfx.blueprints import MESH_PRIMITIVES
    assert {"shockwave", "smoke_dome"} <= set(MESH_PRIMITIVES)
    for name, m in MESH_PRIMITIVES.items():
        assert m.get("geometry"), name
        assert float(m.get("grow", 1.0)) > 0.0, name
        assert m.get("fade") in ("quad_out", "linear", "quad_in", "hold"), (name, m.get("fade"))


def test_generated_vfx_json_matches_generator(blueprints):
    """tools/assets/vfx/blueprints.json 要與產生器同步（忘了跑 `tools.cli vfx2` 就紅燈）。"""
    out = VFX2_JSON / "blueprints.json"
    if not out.exists():
        pytest.skip("素材尚未產生：先跑 python3 -m tools.cli vfx2")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(data["blueprints"]) if isinstance(data["blueprints"], dict) else \
        sorted(b["id"] for b in data["blueprints"])
    ids = set(data["blueprints"]) if isinstance(data["blueprints"], dict) else \
        {b["id"] for b in data["blueprints"]}
    assert ids == set(blueprints), "匯出的特效庫與產生器不一致，請重跑 tools.cli vfx2"
