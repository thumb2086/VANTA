"""Godot 客戶端：素材匯出器測試。"""

import json
import os

import pytest

import tools.godot.export as gexp


@pytest.fixture()
def tmp_export(tmp_path, monkeypatch):
    """把匯出目標導向暫存目錄。"""
    monkeypatch.setattr(gexp, "CLIENT_ASSETS", str(tmp_path / "assets"))
    return tmp_path


def test_export_copies_assets(tmp_export):
    n = gexp.export()
    assert n >= 60
    assert os.path.isdir(str(tmp_export / "assets" / "sfx"))
    assert os.path.isdir(str(tmp_export / "assets" / "bgm"))
    assert os.path.isdir(str(tmp_export / "assets" / "maps"))
    assert os.path.isdir(str(tmp_export / "assets" / "weapons"))
    assert os.path.isdir(str(tmp_export / "assets" / "vfx" / "svg"))
    assert os.path.isdir(str(tmp_export / "assets" / "fx"))


def test_asset_index_valid(tmp_export):
    gexp.export()
    with open(str(tmp_export / "assets" / "asset_index.json"), encoding="utf-8") as f:
        index = json.load(f)
    assert len(index["sfx"]) >= 20
    assert len(index["bgm"]) >= 5
    assert len(index["bgm_meta"]) >= 5
    assert len(index["maps"]) >= 1
    assert len(index["weapons"]) >= 1
    assert len(index["agents"]) >= 4
    assert len(index["agent_portraits"]) >= 4
    # 角色頭像 SVG 已匯出
    for path in index["agent_portraits"][:2]:
        assert path.endswith(".svg")
        assert os.path.isfile(os.path.join(str(tmp_export), path[len("res://"):]))
    for path in index["sfx"][:3]:
        assert path.startswith("res://assets/")
        assert path.endswith((".wav", ".mp3"))
        assert os.path.isfile(os.path.join(str(tmp_export), path[len("res://"):]))


def test_export_dry_does_not_write(tmp_export):
    gexp.export(dry=True)
    assert not os.path.isdir(str(tmp_export / "assets"))


def test_exported_map_loadable(tmp_export):
    gexp.export()
    from tools.maps.export import load_map
    from tools.maps.generator import validate_map

    maps_dir = str(tmp_export / "assets" / "maps")
    for f in os.listdir(maps_dir):
        m = load_map(os.path.join(maps_dir, f))
        ok, issues = validate_map(m)
        assert ok, f
