"""工具鏈：槍皮目錄 / 程序化花紋 / 貼圖合成 / 跨平台一致性測試。

這組測試有兩層意義：
  1. 資料完整性 —— 14 個系列 / 140 支皮膚的色板、價格、特效規格必須自洽。
  2. 「單一資料來源」契約 —— Godot 客戶端與網頁展示台是按同一組常數重寫演算法，
     因此只要工具鏈改了常數／花紋名稱／特效欄位而沒同步到 GDScript，這裡就會紅
     （這類錯誤用眼睛看不出來）。
"""

import json
import math
import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

from tools.godot.export import export as godot_export
from tools.sfx import synth
from tools.skins import catalog, emit, patterns
from tools.skins.png import read_png_size
from tools.vfx.blueprints import BLUEPRINTS, MESH_PRIMITIVES, validate_blueprints
from tools.vfx.decals import DECALS, validate_decals
from tools.vfx.particles import PRESETS, validate_presets
from tools.vfx.sprites import SPRITES, validate_sprites
from tools.vfx.styles import STYLE_META

REPO = pathlib.Path(__file__).resolve().parents[1]
GD_TEXTURE = (REPO / "client" / "scripts" / "procedural_texture.gd").read_text(encoding="utf-8")
GD_FX = (REPO / "client" / "scripts" / "fx_manager.gd").read_text(encoding="utf-8")
GD_MATERIAL = (REPO / "client" / "scripts" / "skin_material.gd").read_text(encoding="utf-8")
GD_GEOMETRY = (REPO / "client" / "scripts" / "weapon_geometry.gd").read_text(encoding="utf-8")

CAT = catalog.collect()          # 唯一資料來源：與遊戲／展示台載入的是同一份
SKINS = CAT["skins"]
COLLECTIONS = CAT["collections"]
TIERS = CAT["tiers"]
COLOR_KEYS = ("primary", "secondary", "accent", "emissive", "rim_color")


def _mean_luma(buf: bytes, size: int, channels: int) -> float:
    total = 0.0
    for i in range(size * size):
        total += (buf[i * channels] + buf[i * channels + 1] + buf[i * channels + 2]) / 3.0
    return total / (255.0 * size * size)


# --------------------------------------------------------------------- #
# 目錄完整性
# --------------------------------------------------------------------- #
def test_catalog_is_clean():
    assert catalog.validate_catalog() == []


def test_vfx_modules_are_clean():
    assert validate_presets() == []
    assert validate_sprites() == []
    assert validate_decals() == []
    assert validate_blueprints() == []


def test_expected_scale():
    assert len(COLLECTIONS) == 14
    assert len(SKINS) == 140
    assert len(COLLECTIONS) * 10 == len(SKINS)
    assert len(PRESETS) == 94
    assert len(SPRITES) == 18
    assert len(DECALS) == 14
    assert len(BLUEPRINTS) == 58


def test_every_tier_defined():
    for s in SKINS:
        assert s["tier"] in TIERS, f"{s['id']} 用了未定義的等級 {s['tier']}"


def test_price_follows_tier():
    """定價 = 稀有度基準 × 武器倍率，取整到 25 VP；整套另有 9 折。

    這是「商店能不能上線」的底線：價格必須可由規則重算，而不是資料裡隨手的數字。
    """
    from tools.skins.catalog import _WEAPON_SHAPE, _price_for

    for sk in SKINS:
        base = int(TIERS[sk["tier"]]["base_price"])
        if base == 0:
            assert int(sk["price_vp"]) == 0, f"{sk['id']}：預設造型不該有價格"
            continue
        assert int(sk["price_vp"]) % 25 == 0, sk["id"]
        mult = float(_WEAPON_SHAPE.get(sk["weapon"], {}).get("price_mult", 1.0))
        if sk["weapon"] in _WEAPON_SHAPE:
            assert int(sk["price_vp"]) == _price_for(sk["tier"], sk["weapon"]), sk["id"]
        assert base * mult * 0.9 <= sk["price_vp"] <= base * mult * 1.1, (sk["id"], base, mult)
    for coll in CAT["collections"]:
        if len(coll["weapons"]) <= 1:
            continue
        total = sum(int(x["price_vp"]) for x in SKINS if x["collection"] == coll["id"])
        assert int(coll["price_vp"]) == int(round(total * 0.9 / 25.0)) * 25, coll["id"]


def test_colorway_colors_are_hex7():
    for s in SKINS:
        for key in COLOR_KEYS:
            v = s["colorway"][key]
            assert isinstance(v, str) and len(v) == 7 and v.startswith("#"), (s["id"], key, v)
            catalog.hex_to_rgb(v)
        for ch in s["chroma"]:
            for key in ("primary", "secondary", "accent", "emissive"):
                v = ch[key]
                assert len(v) == 7 and v.startswith("#"), (s["id"], key, v)


def test_numeric_colorway_ranges():
    for s in SKINS:
        cw = s["colorway"]
        for key in ("metalness", "roughness", "clearcoat", "iridescence", "anisotropy",
                    "pattern_mix", "wear", "rim_strength", "tint_variance"):
            v = float(cw[key])
            assert math.isfinite(v) and 0.0 <= v <= 1.0, (s["id"], key, v)
        assert 0.0 <= float(cw["emissive_strength"]) <= 6.0, s["id"]


def test_skins_cover_real_game_weapons():
    known = set(CAT["weapons"])
    for s in SKINS:
        assert s["weapon"] in known, (s["id"], s["weapon"])
    # 每個系列都要涵蓋主武器／副武器／近戰三類
    for c in COLLECTIONS:
        keys = {s["weapon"] for s in SKINS if s["collection"] == c["id"]}
        assert "vandal" in keys or "phantom" in keys, c["id"]
        assert "knife" in keys, c["id"]


def test_upgrades_are_monotonic():
    for s in SKINS:
        levels = [int(u["level"]) for u in s["upgrades"]]
        assert levels == sorted(set(levels)), s["id"]
        assert all(2 <= lv <= 5 for lv in levels), (s["id"], levels)
        for u in s["upgrades"]:
            assert int(u["radianite"]) > 0 and u.get("kind"), (s["id"], u)
        assert len(s["chroma"]) <= 3


def test_fx_styles_and_blueprints_resolve():
    known_bp = set(BLUEPRINTS)
    known_preset = set(PRESETS)
    for s in SKINS:
        fx = s["fx"]
        assert fx["style"] in STYLE_META, (s["id"], fx["style"])
        for key in ("muzzle", "tracer", "impact", "kill", "smoke"):
            v = fx.get(key, "")
            if v:
                assert v in known_bp or v in known_preset, (s["id"], key, v)
        assert fx["decal"] in DECALS, (s["id"], fx["decal"])
        k = fx.get("sound_key", "")
        if k:
            assert k in synth.SFX_REGISTRY, (s["id"], k)
        for ckey in ("muzzle_color", "tracer_color", "impact_color", "kill_color",
                     "light_color", "shell_color"):
            assert len(str(fx[ckey])) == 7, (s["id"], ckey)


def test_pattern_names_known():
    for s in SKINS:
        assert s["pattern"] in patterns.PATTERNS, (s["id"], s["pattern"])


def test_extras_are_wellformed():
    for s in SKINS:
        for ex in s["extras"]:
            assert ex["kind"], s["id"]
            assert len(ex["pos"]) == 3 and float(ex["size"]) > 0, (s["id"], ex)
            assert ex["color"] in ("emissive", "accent", "rim"), (s["id"], ex["color"])


# --------------------------------------------------------------------- #
# 花紋產生器
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("name", sorted(patterns.PATTERNS))
def test_patterns_are_valid_grids(name):
    size = 24
    grid = patterns.render(name, size, {"seed": 3})
    assert len(grid) == size
    assert all(len(row) == size for row in grid)
    for row in grid:
        for v in row:
            assert math.isfinite(v) and 0.0 <= v <= 1.0, (name, v)


def test_unknown_pattern_falls_back_to_solid():
    grid = patterns.render("no_such_pattern", 8)
    assert all(all(v == grid[0][0] for v in row) for row in grid)


@pytest.mark.parametrize("name", sorted(patterns.PATTERNS))
def test_patterns_are_deterministic(name):
    assert patterns.render(name, 16, {"seed": 11}) == patterns.render(name, 16, {"seed": 11})


# 方向性花紋：v 軸有刻意的漸層／條紋（火焰由下往上燒），不要求上下無縫。
_DIRECTIONAL_PATTERNS = {"flame", "scanline"}


@pytest.mark.parametrize("name", sorted(patterns.PATTERNS))
def test_patterns_tile_without_hard_seam(name):
    """花紋必須能無縫平鋪，判準是「相對」的。

    槍身 UV 的 u 軸繞管套一圈，所以 u=0 與 u=size-1 相鄰；若那條接縫的跳躍比
    花紋內部的最大跳躍還大，模型上就會浮出一條亮線（程序紋路最常見的敗筆）。
    方格類花紋（carbon/circuit）天生就有大階梯，因此以「內部最大跳躍」為基準。
    """
    for size in (32, 64):
        grid = patterns.render(name, size, {"seed": 5})
        wrap_x = max(abs(grid[y][0] - grid[y][size - 1]) for y in range(size))
        inner_x = max(abs(grid[y][x + 1] - grid[y][x])
                      for y in range(size) for x in range(size - 1))
        assert wrap_x <= inner_x * 1.25 + 1e-6, (name, size, "u 軸接縫", round(wrap_x, 3), round(inner_x, 3))
        if name not in _DIRECTIONAL_PATTERNS:
            wrap_y = max(abs(grid[0][x] - grid[size - 1][x]) for x in range(size))
            inner_y = max(abs(grid[y + 1][x] - grid[y][x])
                          for y in range(size - 1) for x in range(size))
            assert wrap_y <= inner_y * 1.25 + 1e-6, (name, size, "v 軸接縫", round(wrap_y, 3), round(inner_y, 3))


def test_noise_primitives_match_constants():
    assert patterns.TILE == 8
    assert patterns.OCTAVES == 4
    assert patterns.GAIN == pytest.approx(0.5)
    for args in [(0, 0, 0), (-3, 7, 11), (255, 255, 3), (1 << 20, -(1 << 19), 99)]:
        assert 0.0 <= patterns.hash2(*args) <= 1.0


def test_value_noise_tiles():
    a = patterns.value_noise(0.0, 0.0, 5, patterns.TILE)
    b = patterns.value_noise(float(patterns.TILE), 0.0, 5, patterns.TILE)
    assert a == pytest.approx(b, abs=1e-9)


def test_fbm_varies_but_stays_in_range():
    vals = [patterns.fbm(x * 0.37, x * 0.91, 2, 4) for x in range(64)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert max(vals) - min(vals) > 0.05


def test_height_to_normal_is_unit_length():
    grid = patterns.render("marble", 16, {"seed": 2})
    for row in patterns.height_to_normal(grid, 2.2):
        for (nx, ny, nz) in row:
            assert abs(math.sqrt(nx * nx + ny * ny + nz * nz) - 1.0) < 1e-6


# --------------------------------------------------------------------- #
# 貼圖合成（品質關鍵規則）
# --------------------------------------------------------------------- #
def test_compose_maps_sizes_and_channels():
    skin = next(s for s in SKINS if s["tier"] in ("premium", "ultra", "exclusive"))
    size = 32
    maps = emit.compose_maps(skin["pattern"], skin["pattern_params"], skin["colorway"],
                             size, seed=7)
    assert set(maps) == {"albedo", "emissive", "normal", "orm"}
    assert len(maps["albedo"]) == size * size * 4
    for key in ("emissive", "normal", "orm"):
        assert len(maps[key]) == size * size * 3
    assert all(maps["albedo"][i * 4 + 3] == 255 for i in range(size * size))


def test_emission_hugs_edges_instead_of_flooding():
    """高級皮的重點：發光只沿脊線。整片發光代表 TEX 常數被改壞。"""
    skin = next(s for s in SKINS if float(s["colorway"]["emissive_strength"]) > 1.5)
    size = 32
    maps = emit.compose_maps(skin["pattern"], skin["pattern_params"], skin["colorway"],
                             size, seed=13)
    lum = _mean_luma(maps["emissive"], size, 3)
    assert 0.01 < lum < 0.45, lum
    lit = sum(1 for i in range(size * size) if maps["emissive"][i * 3] > 200)
    assert lit < size * size * 0.35


def test_standard_skin_does_not_glow():
    skin = next(s for s in SKINS if s["tier"] == "standard")
    maps = emit.compose_maps(skin["pattern"], skin["pattern_params"], skin["colorway"],
                             24, seed=1)
    assert max(maps["emissive"]) == 0


def test_pattern_actually_changes_albedo():
    skin = next(s for s in SKINS if float(s["colorway"]["pattern_mix"]) > 0.3)
    maps = emit.compose_maps(skin["pattern"], skin["pattern_params"], skin["colorway"],
                             32, seed=2)
    lum = _mean_luma(maps["albedo"], 32, 4)
    spread = max(maps["albedo"]) - min(maps["albedo"])
    assert 0.02 < lum < 0.9 and spread > 40, (lum, spread)


def test_wear_reveals_underlying_material():
    skin = max(SKINS, key=lambda s: float(s["colorway"]["wear"]))
    if float(skin["colorway"]["wear"]) < 0.3:
        pytest.skip("目前沒有高磨損色板")
    size = 32
    maps = emit.compose_maps(skin["pattern"], skin["pattern_params"], skin["colorway"],
                             size, seed=3)
    metal = [maps["orm"][i * 3 + 2] for i in range(size * size)]
    assert max(metal) > min(metal) + 8


def test_write_skin_textures(tmp_path):
    skin = SKINS[1]
    files = emit.write_skin_textures("reaver", skin["colorway"], skin["pattern"],
                                     skin["pattern_params"], str(tmp_path), size=16)
    assert len(files) == 4
    for f in files:
        assert pathlib.Path(f).exists()
        w, h, _ch = read_png_size(f)
        assert (w, h) == (16, 16)


def test_collection_card_svg_is_parseable():
    coll = COLLECTIONS[1]
    skins = [s for s in SKINS if s["collection"] == coll["id"]][:4]
    svg = emit.collection_card(coll, skins)
    assert svg.lstrip().startswith("<?xml") and "<svg" in svg
    ET.fromstring(svg)
    assert coll["name"] in svg


# --------------------------------------------------------------------- #
# 輸出 / Godot 匯出
# --------------------------------------------------------------------- #
def test_collect_payload_shape():
    for key in ("version", "tiers", "tier_order", "weapons", "weapon_labels",
                "collections", "skins", "texture_spec", "effects", "stats"):
        assert key in CAT, key
    assert CAT["stats"] == {"collections": len(COLLECTIONS), "skins": len(SKINS)}
    eff = CAT["effects"]
    assert len(eff["particles"]) == len(PRESETS)
    assert len(eff["blueprints"]) == len(BLUEPRINTS)
    assert len(eff["sprites"]) == len(SPRITES)
    assert len(eff["decals"]) == len(DECALS)
    assert "shockwave" in eff["mesh_primitives"]
    assert "soul" in eff["styles"] or "default" in eff["styles"]
    json.dumps(CAT)


def test_emit_writes_json_and_cards(tmp_path):
    out = emit.emit(str(tmp_path), textures=False)
    assert pathlib.Path(out["catalog"]).exists()
    data = json.loads(pathlib.Path(out["catalog"]).read_text(encoding="utf-8"))
    assert len(data["skins"]) == len(SKINS)
    assert len(out["cards"]) == len(COLLECTIONS)


def test_emit_textures_roundtrip(tmp_path):
    out = emit.emit(str(tmp_path), textures=True, texture_size=16,
                    texture_collections=["reaver"])
    assert out["textures"]
    for f in out["textures"]:
        assert pathlib.Path(f).exists()
        w, h, _c = read_png_size(f)
        assert w == h == 16


def test_godot_export_counts_skins():
    total = godot_export(dry=True)
    assert total > 100


# --------------------------------------------------------------------- #
# 跨平台契約：Godot 與工具鏈必須讀同一組名稱／常數
# --------------------------------------------------------------------- #
def test_godot_implements_every_pattern():
    for name in patterns.PATTERNS:
        if name == "solid":
            continue
        assert f"pat_{name}" in GD_TEXTURE, f"Godot 端缺少花紋 pat_{name}"


def test_godot_reads_every_texture_spec_key():
    for key in emit.TEX:
        assert f'"{key}"' in GD_TEXTURE, f"procedural_texture.gd 未讀取 texture_spec.{key}"


def test_godot_noise_constants_match_python():
    def const(name: str) -> float:
        m = re.search(rf"const {name} :?= ([0-9.]+)", GD_TEXTURE)
        assert m, f"Godot 端找不到 const {name}"
        return float(m.group(1))

    assert const("TILE") == patterns.TILE
    assert const("OCTAVES") == patterns.OCTAVES
    assert const("GAIN") == pytest.approx(patterns.GAIN)


def test_godot_handles_every_blueprint_anchor():
    used = set()
    for b in BLUEPRINTS.values():
        for layer in b["layers"]:
            if layer.get("at"):
                used.add(layer["at"])
    for at in sorted(used):
        assert f'"{at}"' in GD_FX, f"fx_manager.gd 沒有處理 at={at}"


def test_godot_handles_every_layer_type():
    used = {layer["type"] for b in BLUEPRINTS.values() for layer in b["layers"]}
    for t in sorted(used):
        assert f'"{t}"' in GD_FX, f"fx_manager.gd 沒有實作圖層 {t}"


def test_godot_material_covers_geometry_roles():
    """圖譜用到的每個 role 都要在 `role_kind()` 的分類表裡（否则該零件永遠用預設材質）。"""
    roles = set(re.findall(r'"role": "([a-z_]+)"', GD_GEOMETRY))
    assert roles, "武器圖譜沒抓到 role"
    src = GD_GEOMETRY
    body = src[src.index("static func role_kind("):]
    body = body[:body.index("\nstatic func") if "\nstatic func" in body else len(body)]
    classified = set(re.findall(r'"([a-z_]+)":\s*"', body)) | \
        set(re.findall(r'(?:match|in)\s*\"([a-z_]+)\"', body))
    for role in ("body", "moving", "metal", "grip", "optic", "lens", "accent", "blade", "mag"):
        assert f'"{role}"' in src, f"role_kind 沒輸出 {role}"
    missing = {r for r in roles if f'"{r}"' not in body}
    assert not missing, f"這些零件角色未列入 role_kind 分類：{sorted(missing)}"
    # weapon_finish 要處理全部九種材質槽
    fin = (REPO / "client" / "scripts" / "weapon_finish.gd").read_text(encoding="utf-8")
    for slot in ("body", "moving", "metal", "grip", "optic", "lens", "accent", "blade", "mag"):
        assert f'"{slot}"' in fin, f"weapon_finish 少了 {slot} 材質"


def test_godot_registry_resolves_slot_presets():
    """style+slot → 粒子預設名 的對應必須真的存在。"""
    for style in STYLE_META:
        for slot in ("muzzle", "tracer", "impact", "kill", "smoke"):
            base = f"{slot}_{style}"
            generic = f"{slot}_default"
            assert base in PRESETS or generic in PRESETS, (style, slot)


def test_mesh_primitives_have_known_geometry():
    for name, prim in MESH_PRIMITIVES.items():
        assert prim["geometry"] in ("ring", "arc", "lines", "sphere"), (name, prim)
        assert "additive" in prim and "grow" in prim
