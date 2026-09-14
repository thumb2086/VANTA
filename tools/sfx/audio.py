"""
tools/sfx/audio.py — WAV 編碼與混音工具
=======================================
以純標準庫（wave + struct）寫入 16-bit PCM mono WAV。
所有合成函式回傳 [-1, 1] 的 float 取樣序列；此處負責編碼與基本 DSP。
"""

from __future__ import annotations

import math
import struct
import wave

SAMPLE_RATE = 44100


def silence(seconds: float) -> list[float]:
    return [0.0] * int(SAMPLE_RATE * seconds)


def tone(
    freq: float,
    duration: float,
    amp: float = 0.6,
    waveform: str = "sine",
    attack: float = 0.002,
    release: float = 0.05,
) -> list[float]:
    """單音：sine / square / saw。附 attack/release 包絡。"""
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        if waveform == "sine":
            v = math.sin(math.tau * freq * t)
        elif waveform == "square":
            v = 1.0 if math.sin(math.tau * freq * t) >= 0 else -1.0
        elif waveform == "saw":
            v = 2.0 * ((freq * t) % 1.0) - 1.0
        else:
            v = math.sin(math.tau * freq * t)
        # 包絡：attack 上升、release 指數衰減
        env = min(1.0, t / attack) if attack > 0 else 1.0
        if release > 0:
            env *= math.exp(-max(0.0, t - duration + release) * 40.0) if t > duration - release else 1.0
        out.append(v * amp * env)
    return out


def noise(n: int, rng=None) -> list[float]:
    """白噪聲。傳入 rng 以保證確定性（否則用全域 random）。"""
    import random

    r = rng if rng is not None else random
    return [r.uniform(-1.0, 1.0) for _ in range(n)]


def lowpass(samples: list[float], cutoff_hz: float) -> list[float]:
    """一階低通（RC 濾波）。"""
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / SAMPLE_RATE
    alpha = dt / (rc + dt)
    out, y = [], 0.0
    for x in samples:
        y += alpha * (x - y)
        out.append(y)
    return out


def highpass(samples: list[float], cutoff_hz: float) -> list[float]:
    """一階高通。"""
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / SAMPLE_RATE
    alpha = rc / (rc + dt)
    out, prev_x, y = [], 0.0, 0.0
    for x in samples:
        y = alpha * (y + x - prev_x)
        prev_x = x
        out.append(y)
    return out


def envelope_exp(samples: list[float], decay_rate: float) -> list[float]:
    """指數衰減包絡：sample[i] *= exp(-decay_rate * i / SR)。"""
    return [s * math.exp(-decay_rate * i / SAMPLE_RATE) for i, s in enumerate(samples)]


def mix(*tracks: list[float]) -> list[float]:
    """疊加多軌（取最長，缺段補零），clamp 到 [-1, 1]。"""
    length = max((len(t) for t in tracks), default=0)
    out = [0.0] * length
    for t in tracks:
        for i, s in enumerate(t):
            out[i] += s
    return [max(-1.0, min(1.0, s)) for s in out]


def write_wav(path: str, samples: list[float], rate: int = SAMPLE_RATE) -> None:
    """寫入 16-bit PCM mono WAV。"""
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767.0)
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def read_wav_info(path: str) -> dict:
    """讀回 WAV 資訊（驗證用）：channel/rate/frames/秒數。"""
    with wave.open(path, "rb") as w:
        return {
            "channels": w.getnchannels(),
            "sample_width": w.getsampwidth(),
            "rate": w.getframerate(),
            "frames": w.getnframes(),
            "seconds": w.getnframes() / w.getframerate(),
        }
