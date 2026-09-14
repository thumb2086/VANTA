"""工具鏈：CLI 整合測試（產生到暫存目錄並驗證產物）。"""

import json
import os

import pytest

import tools.cli as cli


@pytest.fixture()
def assets_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ASSETS_ROOT", str(tmp_path))
    return tmp_path


def test_init_then_all(assets_tmp):
    """跑完 `all` 後，assets/ 下應有音效、VFX、武器、地圖、fx、manifest。"""
    cli.main(["all"])
    assert os.path.isdir(os.path.join(assets_tmp, "sfx"))
    assert os.path.isdir(os.path.join(assets_tmp, "vfx"))
    assert os.path.isdir(os.path.join(assets_tmp, "weapons"))
    assert os.path.isdir(os.path.join(assets_tmp, "maps"))
    assert os.path.isdir(os.path.join(assets_tmp, "fx"))

    # 音效：至少一個 WAV，且可讀
    wavs = os.listdir(os.path.join(assets_tmp, "sfx"))
    assert len(wavs) >= 20
    from tools.sfx.audio import read_wav_info
    info = read_wav_info(os.path.join(assets_tmp, "sfx", "gunshot_rifle.wav"))
    assert info["channels"] == 1 and info["frames"] > 0

    # 武器：JSON 可解析且有最終數值
    wfiles = os.listdir(os.path.join(assets_tmp, "weapons"))
    assert len(wfiles) >= 10
    with open(os.path.join(assets_tmp, "weapons", wfiles[0]), encoding="utf-8") as f:
        wdata = json.load(f)
    assert "stats" in wdata and wdata["stats"]["price"] >= 0

    # 地圖：可載回並通過驗證
    from tools.maps.export import load_map
    from tools.maps.generator import validate_map
    for f in os.listdir(os.path.join(assets_tmp, "maps")):
        m = load_map(os.path.join(assets_tmp, "maps", f))
        ok, issues = validate_map(m)
        assert ok, f

    # manifest
    with open(os.path.join(assets_tmp, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    assert sum(len(v) for v in man["assets"].values()) >= 30


def test_cli_subcommands_individually(assets_tmp):
    cli.main(["sfx"])
    assert len(os.listdir(os.path.join(assets_tmp, "sfx"))) >= 20
    cli.main(["bgm"])
    assert len(os.listdir(os.path.join(assets_tmp, "bgm"))) >= 10     # 5 wav + 5 json
    cli.main(["vfx"])
    assert os.path.isdir(os.path.join(assets_tmp, "vfx", "svg"))
    assert os.path.isdir(os.path.join(assets_tmp, "vfx", "particles"))
    cli.main(["weapons", "--count", "4"])
    assert len(os.listdir(os.path.join(assets_tmp, "weapons"))) == 4
    cli.main(["maps", "--seeds", "1", "2"])
    assert len(os.listdir(os.path.join(assets_tmp, "maps"))) == 2
    cli.main(["agents", "--count", "4", "--seed", "55"])
    agent_files = [f for f in os.listdir(os.path.join(assets_tmp, "agents")) if f.endswith(".json")]
    assert len(agent_files) == 4
    assert os.path.isdir(os.path.join(assets_tmp, "agents", "portraits"))
    cli.main(["fx"])
    assert os.path.isdir(os.path.join(assets_tmp, "fx"))


def test_bgm_wav_valid(assets_tmp):
    """產生的 BGM WAV 可讀、有循環點 sidecar。"""
    from tools.sfx.audio import read_wav_info

    cli.main(["bgm"])
    bgm_dir = os.path.join(assets_tmp, "bgm")
    info = read_wav_info(os.path.join(bgm_dir, "bgm_combat.wav"))
    assert info["channels"] == 1 and info["rate"] == 44100
    assert info["seconds"] > 10
    with open(os.path.join(bgm_dir, "bgm_combat.json"), encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["loop_start_sec"] > 0
    assert meta["loop_start_sec"] < meta["duration_sec"]
    assert meta["bpm"] > 0
