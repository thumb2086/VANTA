"""工具鏈：音效合成器測試（DSP 正確性 / 確定性 / WAV 編碼）。"""

import math

from tools.sfx import synth
from tools.sfx.audio import read_wav_info, write_wav

SR = 44100


def test_tone_frequency_and_length():
    t = synth.tone(440.0, 0.5, waveform="sine")
    assert len(t) == int(0.5 * SR)
    assert any(abs(s) > 0.01 for s in t)          # 非靜音
    # 440Hz 0.5s = 220 週期 → 過零次數 ≈ 440
    zeros = sum(1 for i in range(1, len(t)) if t[i - 1] * t[i] < 0)
    assert 400 < zeros < 480


def test_gunshot_has_crack_and_body():
    s = synth.gunshot("rifle")
    assert len(s) > int(0.1 * SR)
    assert max(abs(v) for v in s) > 0.5           # 峰值明顯
    # 開頭應有高頻爆裂（前 5ms 能量高）
    head = s[: int(0.005 * SR)]
    assert max(abs(v) for v in head) > 0.3


def test_explosion_is_low_and_long():
    e = synth.explosion()
    assert len(e) > int(0.5 * SR)
    # 低頻主導：峰值顯著（非純噪聲小幅度）
    assert max(abs(v) for v in e) > 0.5


def test_determinism_same_seed():
    synth.reseed(42)
    a = synth.gunshot("rifle")
    synth.reseed(42)
    b = synth.gunshot("rifle")
    assert a == b                                  # 位元級相同


def test_different_seeds_differ():
    synth.reseed(1)
    a = synth.gunshot("rifle")
    synth.reseed(2)
    b = synth.gunshot("rifle")
    assert a != b


def test_weapon_class_tones_differ():
    synth.reseed(0)
    a = synth.gunshot("sidearm")
    synth.reseed(0)
    b = synth.gunshot("sniper")
    assert len(b) > len(a)                         # 狙擊槍聲更長


def test_registry_has_required_sfx():
    for required in ("gunshot_rifle", "headshot_confirm", "kill_confirm",
                     "explosion", "spike_planted", "spike_defused", "spike_beep",
                     "round_win", "round_loss", "reload", "footstep", "ui_click"):
        assert required in synth.SFX_REGISTRY


def test_multi_kill_escalates():
    synth.reseed(0)
    base = synth.multi_kill_announce(2)
    synth.reseed(0)
    higher = synth.multi_kill_announce(5)
    assert len(higher) >= len(base)


def test_wav_write_and_read(tmp_path):
    synth.reseed(3)
    path = str(tmp_path / "test.wav")
    write_wav(path, synth.kill_confirm(2))
    info = read_wav_info(path)
    assert info["channels"] == 1
    assert info["sample_width"] == 2
    assert info["rate"] == SR
    assert info["frames"] > 0
    assert info["seconds"] > 0.05


def test_ui_click_short():
    synth.reseed(0)
    assert len(synth.ui_click()) < int(0.05 * SR)


def test_mag_drop_metallic_short():
    """彈匣落地：短促（<0.3s）、高頻金屬音。"""
    synth.reseed(0)
    m = synth.mag_drop()
    assert len(m) < int(0.3 * SR)
    assert max(abs(v) for v in m) > 0.4
    # 高頻金屬 ping：1250/1720Hz 0.13s → 零交叉 ≳ 250
    zc = sum(1 for i in range(1, len(m)) if (m[i - 1] < 0) != (m[i] < 0))
    assert zc > 250


def test_slide_rack_short_snap():
    synth.reseed(0)
    s = synth.slide_rack()
    assert len(s) < int(0.15 * SR)
    assert max(abs(v) for v in s) > 0.3


def test_reload_sounds_in_registry():
    assert "mag_drop" in synth.SFX_REGISTRY
    assert "slide_rack" in synth.SFX_REGISTRY
