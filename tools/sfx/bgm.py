"""
tools/sfx/bgm.py — 程序化背景音樂 (BGM) 產生器
==============================================
以「音樂理論 + 種子化隨機」產生遊戲 BGM，零音源素材、零第三方依賴：

  * 十二平均律音高（midi → 頻率）
  * 音階（minor / phrygian / dorian / major）+ 級數和弦進行
  * 旋律（音階隨機漫步，重拍偏置和弦音）、貝斯、鋪底 Pad、鼓組
  * 5 種風格模板：combat（戰鬥）/ tension（安放後緊張）/ menu（大廳）/
    victory（勝利）/ defeat（敗北）
  * 結構 = 前奏 (intro) + 主循環 (loop) → 輸出「循環點」供客戶端無縫 loop

確定性：所有音樂決策由注入種子的 RNG 驅動；合成皆為純數學 → 同 seed 同 BGM。
"""

from __future__ import annotations

import math
import random

from tools.sfx.audio import SAMPLE_RATE, highpass, lowpass, noise

# --------------------------------------------------------------------- #
# 音樂理論
# --------------------------------------------------------------------- #
def midi_freq(n: float) -> float:
    """十二平均律：A4 (69) = 440Hz。"""
    return 440.0 * 2.0 ** ((n - 69.0) / 12.0)


# 音階（半音間隔，相對根音）
SCALES: dict[str, list[int]] = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
}

# 級數 → 音階索引（大小寫表示和弦性質：大寫=大三和弦，小寫=小三和弦）
DEGREE_IDX = {
    "I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6,
    "i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6,
}


def chord_tones(root_midi: int, degree: str, scale: str) -> list[int]:
    """依根音 + 級數和弦回傳和弦音（三和弦）。"""
    semi = SCALES[scale][DEGREE_IDX[degree]]
    r = root_midi + semi
    third = 4 if degree.isupper() else 3        # 大三度 / 小三度
    return [r, r + third, r + 7]


# --------------------------------------------------------------------- #
# 風格模板
# --------------------------------------------------------------------- #
GENRES: dict[str, dict] = {
    "combat": dict(bpm=142, scale="phrygian", root=57,          # A 調
                   progression=["i", "VI", "III", "VII"],
                   drum="four_floor", lead=True, pad=False,
                   bars_intro=2, bars_loop=8, chord_bars=2),
    "tension": dict(bpm=100, scale="minor", root=57,
                    progression=["i", "VI", "III", "VII"],
                    drum="half_time", lead=True, pad=True,
                    bars_intro=2, bars_loop=8, chord_bars=2),
    "menu": dict(bpm=76, scale="dorian", root=57,
                 progression=["i", "iv", "VII", "III"],
                 drum="none", lead=False, pad=True,
                 bars_intro=2, bars_loop=8, chord_bars=4),
    "victory": dict(bpm=122, scale="major", root=60,           # C 大調
                    progression=["I", "IV", "V", "I"],
                    drum="four_floor", lead=True, pad=False,
                    bars_intro=2, bars_loop=8, chord_bars=2),
    "defeat": dict(bpm=78, scale="minor", root=57,
                   progression=["i", "VI", "iv", "V"],
                   drum="half_time", lead=True, pad=True,
                   bars_intro=2, bars_loop=8, chord_bars=2),
}


def genre_names() -> list[str]:
    return sorted(GENRES)


# --------------------------------------------------------------------- #
# 節奏圖案（種子化）
# --------------------------------------------------------------------- #
def _drum_pattern(rng: random.Random, kind: str, total_steps: int) -> dict:
    """回傳 {kick: set, snare: set, hat: set, hat_open: set}（16 分音符步）。"""
    kick, snare, hat, hat_open = set(), set(), set(), set()
    if kind == "four_floor":
        for s in range(0, total_steps, 4):      # 每拍一個大鼓
            kick.add(s)
        for s in range(0, total_steps, 16):     # 每小節 2、4 拍小鼓
            snare.add(s + 8)
            snare.add(s + 24)
        for s in range(0, total_steps, 2):      # 8 分音符 hi-hat
            if rng.random() < 0.85:
                hat.add(s)
            if s % 16 == 12 and rng.random() < 0.4:   # 偶爾開鈸
                hat_open.add(s + 2)
    elif kind == "half_time":
        for s in range(0, total_steps, 16):     # 半拍：1、3 拍大鼓
            kick.add(s)
            kick.add(s + 8)
            snare.add(s + 8)                    # 3 拍小鼓（half-time 感）
        for s in range(0, total_steps, 4):
            if rng.random() < 0.7:
                hat.add(s)
    return {"kick": kick, "snare": snare, "hat": hat, "hat_open": hat_open}


def _gen_melody(rng: random.Random, root: int, scale: str,
                chords: list[tuple[int, list[int]]], total_steps: int) -> list[tuple[int, int, int]]:
    """旋律：音階隨機漫步 + 重拍吸附和弦音。回傳 [(start_step, len_16th, midi)]。"""
    semis = SCALES[scale]
    base = root + 12                             # 高八度起點
    cur_idx = rng.randrange(len(semis))
    notes: list[tuple[int, int, int]] = []
    step = 0
    while step < total_steps:
        # 音符長度（16 分音符）
        length = rng.choice((1, 1, 2, 2, 4))
        # 隨機漫步（±2 個音階音）
        cur_idx = max(0, min(len(semis) - 1, cur_idx + rng.randint(-2, 2)))
        midi = base + semis[cur_idx]
        # 重拍（每小節第一拍）吸附到和弦音
        if step % 16 == 0:
            chord = None
            for cs, tones in chords:
                if cs <= step < cs + 16:
                    chord = tones
                    break
            if chord and rng.random() < 0.8:
                # 找離目前音最近的和弦音（同八度）
                nearest = min(chord, key=lambda c: abs((c + 12) - midi))
                midi = nearest + 12
        if rng.random() > 0.12:                  # 偶爾休止
            notes.append((step, min(length, total_steps - step), midi))
        step += length
    return notes


def _gen_bass(rng: random.Random, chords: list[tuple[int, list[int]]],
              total_steps: int) -> list[tuple[int, int, int]]:
    """貝斯：跟和弦根音，每拍或半拍。"""
    out: list[tuple[int, int, int]] = []
    for cs, tones in chords:
        root_note = tones[0] - 12
        for off in range(0, 16, 4):              # 每小節 4 拍
            step = cs + off
            if step >= total_steps:
                break
            # 偶爾八度變化 / 過門音
            note = root_note
            if off == 12 and rng.random() < 0.5:
                note = tones[0] - 24
            out.append((step, 4, note))
    return out


# --------------------------------------------------------------------- #
# 音色合成（純 DSP）
# --------------------------------------------------------------------- #
def _env(n: int, attack: float, release_rate: float) -> list[float]:
    """AD 包絡：短攻擊 + 指數衰減。"""
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        a = min(1.0, t / attack) if attack > 0 else 1.0
        out.append(a * math.exp(-release_rate * t))
    return out


def _kick() -> list[float]:
    """大鼓：正弦音高掃掠 140→50Hz，快速衰減（無噪聲 → 不需 rng）。"""
    n = int(0.22 * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 50.0 + 90.0 * math.exp(-40.0 * t)
        out.append(math.sin(math.tau * f * t) * math.exp(-18.0 * t))
    return out


def _snare(rng: random.Random) -> list[float]:
    """小鼓：高通噪聲（種子化）+ 低頻身體。"""
    n = int(0.16 * SAMPLE_RATE)
    body = [math.sin(math.tau * 180.0 * i / SAMPLE_RATE) * math.exp(-30.0 * i / SAMPLE_RATE)
            for i in range(n)]
    crack = [s * math.exp(-35.0 * i / SAMPLE_RATE)
             for i, s in enumerate(highpass(noise(n, rng), 1600.0))]
    out = [0.6 * body[i] + 0.7 * crack[i] for i in range(n)]
    return out


def _hat(rng: random.Random, open_: bool = False) -> list[float]:
    """hi-hat：高通噪聲（種子化）短音。"""
    dur = 0.35 if open_ else 0.06
    n = int(dur * SAMPLE_RATE)
    return [s * math.exp(-60.0 * i / SAMPLE_RATE)
            for i, s in enumerate(highpass(noise(n, rng), 7000.0))]


def _bass_note(freq: float, dur: float) -> list[float]:
    """貝斯：基頻正弦 + 二次諧波，輕低通。"""
    n = int(dur * SAMPLE_RATE)
    env = _env(n, 0.005, 6.0)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        v = math.sin(math.tau * freq * t) + 0.3 * math.sin(math.tau * 2 * freq * t)
        out.append(0.8 * v * env[i])
    return lowpass(out, 900.0)


def _lead_note(freq: float, dur: float, wave: str = "square") -> list[float]:
    """主旋律：方波/鋸齒波 + 低通 + 包絡。"""
    n = int(dur * SAMPLE_RATE)
    env = _env(n, 0.008, 5.0)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        ph = (freq * t) % 1.0
        if wave == "square":
            v = 1.0 if ph < 0.5 else -1.0
        else:
            v = 2.0 * ph - 1.0
        out.append(0.5 * v * env[i])
    return lowpass(out, min(4000.0, freq * 5.0))


def _pad_chord(freqs: list[float], dur: float) -> list[float]:
    """鋪底和弦：失諧鋸齒疊加 + 慢起音 + 低通。"""
    n = int(dur * SAMPLE_RATE)
    voices = []
    for f in freqs:
        for det in (-0.6, 0.6):                 # 失諧 → 寬廣感
            out = []
            for i in range(n):
                t = i / SAMPLE_RATE
                ph = ((f + det) * t) % 1.0
                out.append(2.0 * ph - 1.0)
            voices.append(out)
    mixed = [sum(v[i] for v in voices) / max(1, len(voices)) for i in range(n)]
    # 慢起音包絡
    atk_n = int(0.25 * SAMPLE_RATE)
    for i in range(n):
        a = min(1.0, i / max(1, atk_n)) * math.exp(-2.5 * i / n)
        mixed[i] *= a * 0.9
    return lowpass(mixed, 900.0)


# --------------------------------------------------------------------- #
# 渲染（結構 = 前奏 + 循環）
# --------------------------------------------------------------------- #
def _place(buf: list[float], start: int, chunk: list[float], gain: float) -> None:
    for i, s in enumerate(chunk):
        idx = start + i
        if 0 <= idx < len(buf):
            buf[idx] += s * gain


def render_genre(seed: int, genre: str = "combat") -> tuple[list[float], dict]:
    """產生一首 BGM。回傳 (單聲道取樣, 元資料含 loop_start_sec)。"""
    if genre not in GENRES:
        raise KeyError(f"unknown bgm genre: {genre}")
    cfg = GENRES[genre]
    rng = random.Random(seed)

    bpm = cfg["bpm"]
    beat = 60.0 / bpm
    step16 = beat / 4.0                          # 16 分音符時長
    scale = cfg["scale"]
    root = cfg["root"]

    bars_intro, bars_loop = cfg["bars_intro"], cfg["bars_loop"]
    bars_total = bars_intro + bars_loop
    total_steps = bars_total * 16
    duration = total_steps * step16

    # 和弦安排（每 chord_bars 小節換一個，循環）
    prog = cfg["progression"]
    chord_bars = cfg["chord_bars"]
    chords: list[tuple[int, list[int]]] = []
    for bar in range(bars_total):
        deg = prog[(bar // chord_bars) % len(prog)]
        tones = chord_tones(root, deg, scale)
        chords.append((bar * 16, tones))

    # 生成各聲部
    melody = _gen_melody(rng, root, scale, chords, total_steps) if cfg["lead"] else []
    bass = _gen_bass(rng, chords, total_steps)
    drums = _drum_pattern(rng, cfg["drum"], total_steps)

    # 渲染緩衝
    buf = [0.0] * int(duration * SAMPLE_RATE)

    # 鼓組（前奏減弱；噪聲音色使用種子化 rng → 確定性）
    for s in drums["kick"]:
        g = 0.9 if s >= bars_intro * 16 else 0.4
        _place(buf, int(s * step16 * SAMPLE_RATE), _kick(), g)
    for s in drums["snare"]:
        g = 0.8 if s >= bars_intro * 16 else 0.35
        _place(buf, int(s * step16 * SAMPLE_RATE), _snare(rng), g)
    for s in drums["hat"]:
        g = 0.45 if s >= bars_intro * 16 else 0.2
        _place(buf, int(s * step16 * SAMPLE_RATE), _hat(rng), g)
    for s in drums["hat_open"]:
        _place(buf, int(s * step16 * SAMPLE_RATE), _hat(rng, open_=True), 0.3)

    # 貝斯
    for s, ln, midi in bass:
        g = 0.9 if s >= bars_intro * 16 else 0.5
        _place(buf, int(s * step16 * SAMPLE_RATE), _bass_note(midi_freq(midi), ln * step16 + 0.02), g)

    # 主旋律
    for s, ln, midi in melody:
        _place(buf, int(s * step16 * SAMPLE_RATE), _lead_note(midi_freq(midi), ln * step16 + 0.02), 0.55)

    # 鋪底 Pad（每小節一個和弦）
    if cfg["pad"]:
        for cs, tones in chords:
            freqs = [midi_freq(t) for t in tones]
            _place(buf, int(cs * step16 * SAMPLE_RATE), _pad_chord(freqs, 16 * step16), 0.4)

    # 軟削波 + 歸一化
    peak = max(1e-9, max(abs(s) for s in buf))
    norm = 0.85 / peak
    buf = [math.tanh(s * norm) / math.tanh(1.0) * 0.85 for s in buf]

    loop_start = bars_intro * 16 * step16
    meta = {
        "name": f"bgm_{genre}",
        "genre": genre,
        "bpm": bpm,
        "scale": scale,
        "root_midi": root,
        "bars_intro": bars_intro,
        "bars_loop": bars_loop,
        "duration_sec": round(duration, 3),
        "loop_start_sec": round(loop_start, 3),
        "seed": seed,
    }
    return buf, meta
