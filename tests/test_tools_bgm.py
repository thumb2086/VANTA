"""工具鏈：程序化 BGM 產生器測試（音樂理論 / 確定性 / 循環點 / CLI）。"""

import math

import pytest

from tools.sfx import bgm
from tools.sfx.audio import read_wav_info, write_wav


# --------------------------------------------------------------------- #
# 音樂理論
# --------------------------------------------------------------------- #
def test_midi_freq_standard():
    assert math.isclose(bgm.midi_freq(69), 440.0, rel_tol=1e-9)      # A4
    assert math.isclose(bgm.midi_freq(81), 880.0, rel_tol=1e-9)      # A5
    assert math.isclose(bgm.midi_freq(57), 220.0, rel_tol=1e-9)      # A3


def test_chord_tones_minor_and_major():
    # A 小調 i = Am (A, C, E)
    am = bgm.chord_tones(57, "i", "minor")
    assert am == [57, 60, 64]
    # A 小調 VI = F (F, A, C)
    f = bgm.chord_tones(57, "VI", "minor")
    assert f == [65, 69, 72]
    # C 大調 I = C (C, E, G)
    c = bgm.chord_tones(60, "I", "major")
    assert c == [60, 64, 67]


def test_genres_defined():
    for g in ("combat", "tension", "menu", "victory", "defeat"):
        assert g in bgm.GENRES
    assert "phrygian" in bgm.SCALES


# --------------------------------------------------------------------- #
# 確定性與渲染
# --------------------------------------------------------------------- #
def test_render_deterministic():
    a, _ = bgm.render_genre(seed=7, genre="combat")
    b, _ = bgm.render_genre(seed=7, genre="combat")
    assert a == b


def test_different_seeds_differ():
    a, _ = bgm.render_genre(seed=1, genre="combat")
    b, _ = bgm.render_genre(seed=2, genre="combat")
    assert a != b


def test_all_genres_render_valid():
    for g in bgm.genre_names():
        samples, meta = bgm.render_genre(seed=3, genre=g)
        assert len(samples) > 0
        assert max(abs(s) for s in samples) > 0.2          # 非靜音
        assert max(abs(s) for s in samples) <= 1.0         # 不削波過頭
        # 時長符合 BPM 計算
        beat = 60.0 / meta["bpm"]
        expected = (meta["bars_intro"] + meta["bars_loop"]) * 4 * beat
        assert math.isclose(meta["duration_sec"], expected, rel_tol=0.02)


def test_loop_start_correct():
    """循環點 = 前奏結束位置（intro 小節數 × 4 拍 × 拍長）。"""
    for g in ("combat", "menu"):
        _, meta = bgm.render_genre(seed=5, genre=g)
        beat = 60.0 / meta["bpm"]
        expected = meta["bars_intro"] * 4 * beat
        # meta 已四捨五入至 3 位小數 → 用 abs_tol 比較
        assert math.isclose(meta["loop_start_sec"], expected, abs_tol=0.001)
        assert 0.0 < meta["loop_start_sec"] < meta["duration_sec"]


def test_genres_sound_different():
    c, _ = bgm.render_genre(seed=9, genre="combat")
    m, _ = bgm.render_genre(seed=9, genre="menu")
    assert len(c) != len(m)          # BPM 不同 → 長度不同
    assert c != m


def _zero_crossing_rate(samples: list[float]) -> float:
    """每秒零交叉次數：高頻成分（鼓/鈸）遠高於低頻鋪底。"""
    n = len(samples)
    zc = sum(1 for i in range(1, n) if (samples[i - 1] < 0.0) != (samples[i] < 0.0))
    return zc / (n / 44100.0)


def test_combat_has_drums_menu_pad():
    """combat 含高頻鼓組（零交叉率高）；menu 是低頻鋪底（零交叉率低）。"""
    c_samples, c_meta = bgm.render_genre(seed=1, genre="combat")
    m_samples, m_meta = bgm.render_genre(seed=1, genre="menu")
    c_loop = c_samples[int(c_meta["loop_start_sec"] * 44100):]
    m_loop = m_samples[int(m_meta["loop_start_sec"] * 44100):]
    assert _zero_crossing_rate(c_loop) > _zero_crossing_rate(m_loop) * 1.5
    assert m_meta["duration_sec"] > c_meta["duration_sec"]   # menu 更慢 BPM


def test_wav_write_and_read(tmp_path):
    samples, meta = bgm.render_genre(seed=2, genre="victory")
    path = str(tmp_path / "bgm_test.wav")
    write_wav(path, samples)
    info = read_wav_info(path)
    assert info["channels"] == 1
    assert info["rate"] == 44100
    assert math.isclose(info["seconds"], meta["duration_sec"], rel_tol=0.02)


def test_unknown_genre_rejected():
    with pytest.raises(KeyError):
        bgm.render_genre(seed=1, genre="nope")
