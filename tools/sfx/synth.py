"""
tools/sfx/synth.py — 遊戲音效合成器（DSP 數學合成，零素材依賴）
================================================================
以「參數化合成」產生《特戰英豪》風格的音效：
  * 槍聲      = 高頻爆裂（短噪聲）+ 低頻軀體衰減（依武器類別調整音色）
  * 爆炸      = 低頻隆隆（深噪聲）+ 60Hz 次聲
  * 爆頭確認  = 高頻「叮」（正弦 + 快速衰減）
  * 腳步      = 短促低頻脈衝（依移動狀態調整間隔）
  * UI / 技能 / Spike / 回合 等系統音效

每個音效都是「函式」，可程式化調整參數（音量/音高/長度）→ 滿足
「可程式化音效」需求。全部確定性：依賴工具層注入的 seed（見 reseed）。
"""

from __future__ import annotations

import random

from tools.sfx.audio import (
    SAMPLE_RATE,
    envelope_exp,
    highpass,
    lowpass,
    mix,
    noise,
    silence,
    tone,
)

_rng = random.Random(0)


def reseed(seed: int = 0) -> None:
    """設定合成隨機種子 → 相同 seed 產生相同音效（可重現）。"""
    _rng.seed(seed)


def _noise(n: int) -> list[float]:
    return [_rng.uniform(-1.0, 1.0) for _ in range(n)]


# --------------------------------------------------------------------- #
# 武器音效
# --------------------------------------------------------------------- #
# 每類武器的音色參數：高頻爆裂強度 / 低頻衰減率 / 時長比例
_WEAPON_TONES = {
    "sidearm": (0.8, 55.0, 0.9),
    "smg": (0.9, 45.0, 1.0),
    "rifle": (1.0, 38.0, 1.1),
    "sniper": (1.3, 26.0, 1.5),
    "shotgun": (0.7, 20.0, 1.3),
    "heavy": (1.1, 22.0, 1.4),
    "melee": (0.5, 80.0, 0.4),
}


def gunshot(weapon_class: str = "rifle") -> list[float]:
    """槍聲：短高頻爆裂 + 低頻軀體衰減。"""
    crack_amp, body_decay, length = _WEAPON_TONES.get(weapon_class, _WEAPON_TONES["rifle"])
    crack = envelope_exp(highpass(_noise(int(0.006 * SAMPLE_RATE)), 2200.0), 700.0)
    body = envelope_exp(lowpass(_noise(int(0.22 * length * SAMPLE_RATE)), 750.0), body_decay)
    return mix([s * 0.9 * crack_amp for s in crack], [s * 0.6 for s in body])


def sniper_shot() -> list[float]:
    return mix(gunshot("sniper"), [s * 0.3 for s in tone(90.0, 0.3, 0.5, "sine", release=0.25)])


def reload() -> list[float]:
    """換彈：兩次短促機械咔噠。"""
    click1 = envelope_exp(highpass(_noise(int(0.015 * SAMPLE_RATE)), 1800.0), 300.0)
    click2 = envelope_exp(highpass(_noise(int(0.02 * SAMPLE_RATE)), 1600.0), 250.0)
    return mix(click1 + silence(0.12), silence(0.12) + click2 + silence(0.2))


def mag_drop() -> list[float]:
    """彈匣落地：金屬碰撞（短促高頻餘韻 + 二次彈跳）。"""
    # 金屬 ping：兩三個高頻衰減正弦 + 噪聲瞬態
    ping1 = [s * 0.5 for s in tone(1250.0, 0.07, 0.5, "sine", release=0.06)]
    ping2 = [s * 0.3 for s in tone(1720.0, 0.05, 0.4, "sine", release=0.04)]
    clank = envelope_exp(highpass(_noise(int(0.02 * SAMPLE_RATE)), 2400.0), 400.0)
    # 落地二次彈跳（更小、更短）
    bounce = [s * 0.25 for s in tone(980.0, 0.04, 0.3, "sine", release=0.03)]
    return mix(
        clank,
        [s * 0.8 for s in ping1],
        [s * 0.5 for s in ping2],
        silence(0.09) + bounce,
    )


def slide_rack() -> list[float]:
    """拉滑套：機械滑動（短噪聲 + 高頻咔）。"""
    slide = envelope_exp(highpass(_noise(int(0.03 * SAMPLE_RATE)), 1400.0), 200.0)
    snap = envelope_exp(highpass(_noise(int(0.012 * SAMPLE_RATE)), 3000.0), 500.0)
    return mix(slide, silence(0.03) + snap)


def empty_click() -> list[float]:
    """空槍。"""
    return envelope_exp(highpass(_noise(int(0.01 * SAMPLE_RATE)), 3000.0), 400.0)


# --------------------------------------------------------------------- #
# 命中 / 擊殺
# --------------------------------------------------------------------- #
def body_hit() -> list[float]:
    """命中肉體：低頻短悶響。"""
    return envelope_exp(lowpass(_noise(int(0.05 * SAMPLE_RATE)), 500.0), 40.0)


def headshot_confirm() -> list[float]:
    """爆頭確認：高頻「叮」+ 微低頻。"""
    ding = tone(1568.0, 0.12, 0.35, "sine", release=0.1)      # G6
    ding2 = tone(2093.0, 0.15, 0.2, "sine", release=0.12)     # C7
    return mix(ding, [s * 0.5 for s in ding2])


def kill_confirm(streak: int = 1) -> list[float]:
    """擊殺確認：依連殺數遞升音調（連殺音效）。"""
    base = 660.0 + streak * 90.0
    return mix(
        tone(base, 0.1, 0.3, "square", release=0.08),
        tone(base * 1.5, 0.16, 0.2, "sine", release=0.12),
    )


def multi_kill_announce(streak: int) -> list[float]:
    """多連殺宣告：遞升三連音。"""
    parts = []
    for i in range(3):
        f = 440.0 + streak * 60.0 + i * 132.0
        parts.append(silence(i * 0.09) + tone(f, 0.08, 0.3, "square", release=0.06))
    return mix(*parts) if parts else [0.0]


def damage_taken() -> list[float]:
    """受傷：低沉悶響。"""
    return envelope_exp(lowpass(_noise(int(0.08 * SAMPLE_RATE)), 400.0), 28.0)


# --------------------------------------------------------------------- #
# 環境 / 移動
# --------------------------------------------------------------------- #
def footstep() -> list[float]:
    """腳步：短促低頻脈衝。"""
    return envelope_exp(lowpass(_noise(int(0.03 * SAMPLE_RATE)), 700.0), 90.0)


def landing() -> list[float]:
    """落地。"""
    return envelope_exp(lowpass(_noise(int(0.06 * SAMPLE_RATE)), 500.0), 40.0)


def explosion() -> list[float]:
    """爆炸：低頻深噪聲 + 次聲隆隆。"""
    boom = envelope_exp(lowpass(_noise(int(0.8 * SAMPLE_RATE)), 300.0), 6.0)
    rumble = envelope_exp(tone(60.0, 0.9, 0.5, "sine", release=0.6), 4.0)
    return mix([s * 1.1 for s in boom], [s * 0.8 for s in rumble])


# --------------------------------------------------------------------- #
# 技能
# --------------------------------------------------------------------- #
def ult_ready_chime() -> list[float]:
    """終點球就緒：三音上行鐘聲（G→B→E），短、亮、不蓋槍聲。

    注意：這兩個音效**不碰全域隨機流**（`_rng`）。`cmd_sfx` 依 key 排序產生並共用
    同一條流，若新鍵中途取用隨機數，字串排序在它後面的音效會跟著漂移位元組
    （real case：venom_shot）。所以這裡自備定種子 rng。
    """
    import math

    total = int(0.5 * SAMPLE_RATE)
    out = [0.0] * total
    for freq, start, dur in ((784.0, 0.00, 0.22), (988.0, 0.07, 0.22), (1318.5, 0.14, 0.30)):
        off = int(start * SAMPLE_RATE)
        n = min(int(dur * SAMPLE_RATE), total - off)
        for i in range(n):
            t = i / SAMPLE_RATE
            env = math.exp(-6.5 * t)
            # 基頻 + 二次泛音 → 有「鐘」的質感而不是純音
            out[off + i] += 0.30 * env * (math.sin(math.tau * freq * t)
                                          + 0.25 * math.sin(math.tau * freq * 2.0 * t))
    return [max(-1.0, min(1.0, v)) for v in out]


def ult_cast() -> list[float]:
    """終點球施放：低頻隆隆 + 58Hz 次聲 + 高頻閃音（有重量但不長時間壓槍聲）。"""
    import math

    n = int(0.75 * SAMPLE_RATE)
    out = [0.0] * n
    rng = random.Random(0xCA57)
    body = envelope_exp(lowpass([rng.uniform(-1.0, 1.0) for _ in range(int(0.5 * SAMPLE_RATE))],
                               260.0), 7.0)
    for i, v in enumerate(body):
        out[i] += 0.55 * v
    for i in range(int(0.45 * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        out[i] += 0.5 * math.exp(-6.0 * t) * math.sin(math.tau * 58.0 * t)
    for i in range(int(0.3 * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        out[i] += 0.18 * math.exp(-12.0 * t) * math.sin(math.tau * 2100.0 * t)
    return [max(-1.0, min(1.0, v)) for v in out]


def ability_cast() -> list[float]:
    """技能施放：上升滑音。"""
    import math

    n = int(0.25 * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 300.0 + 900.0 * (i / n)                     # 滑音 300→1200
        out.append(0.3 * math.sin(math.tau * f * t) * (1.0 - i / n))
    return out


def flash_explode() -> list[float]:
    """閃光彈爆炸：尖銳高頻。"""
    return envelope_exp(highpass(_noise(int(0.3 * SAMPLE_RATE)), 1500.0), 12.0)


def smoke_puff() -> list[float]:
    """煙霧釋放：低沉氣聲。"""
    return envelope_exp(lowpass(_noise(int(0.4 * SAMPLE_RATE)), 600.0), 8.0)


def trap_trigger() -> list[float]:
    """陷阱觸發：機械卡榫 + 電鳴。"""
    snap = envelope_exp(highpass(_noise(int(0.02 * SAMPLE_RATE)), 2000.0), 250.0)
    buzz = tone(220.0, 0.25, 0.25, "saw", release=0.2)
    return mix(snap, buzz)


def concuss_effect() -> list[float]:
    """暈眩：低鳴。"""
    return mix(tone(140.0, 0.4, 0.35, "sine", release=0.35), [s * 0.4 for s in tone(70.0, 0.5, 0.3, "sine", release=0.45)])


# --------------------------------------------------------------------- #
# Spike
# --------------------------------------------------------------------- #
def spike_beep() -> list[float]:
    """Spike 倒數嗶聲。"""
    return tone(880.0, 0.07, 0.25, "square", release=0.05)


def spike_planted() -> list[float]:
    """安放完成：上升三連音。"""
    return mix(
        tone(523.0, 0.1, 0.3, "square", release=0.08),
        silence(0.1) + tone(659.0, 0.1, 0.3, "square", release=0.08),
        silence(0.2) + tone(784.0, 0.14, 0.3, "square", release=0.1),
    )


def spike_defused() -> list[float]:
    """拆除成功：下降三連音。"""
    return mix(
        tone(784.0, 0.1, 0.3, "square", release=0.08),
        silence(0.1) + tone(659.0, 0.1, 0.3, "square", release=0.08),
        silence(0.2) + tone(523.0, 0.14, 0.3, "square", release=0.1),
    )


def spike_exploded() -> list[float]:
    return explosion()


# --------------------------------------------------------------------- #
# 回合 / UI
# --------------------------------------------------------------------- #
def round_win() -> list[float]:
    """回合勝利：高昂雙音。"""
    return mix(tone(880.0, 0.14, 0.3, "square", release=0.1),
               silence(0.12) + tone(1174.0, 0.2, 0.3, "square", release=0.14))


def round_loss() -> list[float]:
    """回合敗北：低沉雙音。"""
    return mix(tone(440.0, 0.14, 0.3, "sine", release=0.1),
               silence(0.12) + tone(330.0, 0.2, 0.3, "sine", release=0.14))


def ui_click() -> list[float]:
    """UI 點擊。"""
    return envelope_exp(highpass(_noise(int(0.008 * SAMPLE_RATE)), 2500.0), 500.0)


def ui_buy() -> list[float]:
    """購買成功。"""
    return mix(tone(660.0, 0.07, 0.25, "square", release=0.05),
               silence(0.05) + tone(990.0, 0.1, 0.25, "square", release=0.07))


def ui_error() -> list[float]:
    """購買失敗（錢不夠）。"""
    return tone(220.0, 0.12, 0.3, "square", release=0.1)



# --------------------------------------------------------------------- #
# 槍皮招牌音效（skin signature shots）
# --------------------------------------------------------------------- #
# 每套高級造型在《特戰英豪》都有獨特射擊音色。這裡以「合成簽名」描述：
#   crack  : 高頻爆裂的起始頻率（Hz，越低越悶）
#   body   : 低頻軀體衰減率（越大越短促）
#   tonal  : 附加純音頻率（0 = 無），製造「能量／雷射」感
#   tonal2 : 二次泛音頻率
#   sweep  : 音高滑動倍率（>1 上揚、<1 下沈）
#   tail   : 餘韻長度（秒）
#   grit   : 失真強度（0..1）
#   gain   : 輸出增益
SKIN_SIGNATURES: dict[str, dict] = {
    "reaver_shot": {"crack": 900.0, "body": 30.0, "tonal": 110.0, "tonal2": 0.0,
                    "sweep": 0.62, "tail": 0.30, "grit": 0.45, "gain": 1.0},
    "prime_shot": {"crack": 1500.0, "body": 40.0, "tonal": 320.0, "tonal2": 640.0,
                   "sweep": 1.35, "tail": 0.16, "grit": 0.12, "gain": 0.95},
    "sentinels_shot": {"crack": 1750.0, "body": 34.0, "tonal": 880.0, "tonal2": 1320.0,
                       "sweep": 1.2, "tail": 0.26, "grit": 0.05, "gain": 0.9},
    "dragon_roar": {"crack": 520.0, "body": 16.0, "tonal": 78.0, "tonal2": 132.0,
                    "sweep": 0.7, "tail": 0.55, "grit": 0.75, "gain": 1.1},
    "elderflame_shot": {"crack": 470.0, "body": 14.0, "tonal": 62.0, "tonal2": 124.0,
                        "sweep": 0.66, "tail": 0.62, "grit": 0.8, "gain": 1.15},
    "glitch_shot": {"crack": 2100.0, "body": 60.0, "tonal": 440.0, "tonal2": 466.0,
                    "sweep": 1.9, "tail": 0.10, "grit": 0.6, "gain": 0.85},
    "laser_shot": {"crack": 2400.0, "body": 70.0, "tonal": 1600.0, "tonal2": 2400.0,
                   "sweep": 0.45, "tail": 0.12, "grit": 0.0, "gain": 0.8},
    "ice_shot": {"crack": 1900.0, "body": 48.0, "tonal": 1560.0, "tonal2": 2340.0,
                 "sweep": 1.5, "tail": 0.22, "grit": 0.08, "gain": 0.85},
    "venom_shot": {"crack": 700.0, "body": 24.0, "tonal": 180.0, "tonal2": 0.0,
                   "sweep": 0.8, "tail": 0.34, "grit": 0.35, "gain": 0.95},
    "stardust_shot": {"crack": 1600.0, "body": 36.0, "tonal": 1046.0, "tonal2": 1568.0,
                      "sweep": 1.28, "tail": 0.30, "grit": 0.04, "gain": 0.85},
    "araxys_shot": {"crack": 600.0, "body": 20.0, "tonal": 92.0, "tonal2": 150.0,
                    "sweep": 0.74, "tail": 0.42, "grit": 0.6, "gain": 1.05},
    "katana_swing": {"crack": 2600.0, "body": 90.0, "tonal": 0.0, "tonal2": 0.0,
                     "sweep": 1.1, "tail": 0.18, "grit": 0.02, "gain": 0.7},
}


def skin_shot(style: str = "reaver_shot") -> list[float]:
    """槍皮招牌射擊聲：爆裂 + 低頻軀體 + 音高滑動 + 可選失真與餘韻。"""
    import math

    p = SKIN_SIGNATURES.get(style)
    if p is None:
        return gunshot("rifle")
    dur = 0.10 + p["tail"]
    n = int(dur * SAMPLE_RATE)
    grit = p["grit"]
    crack = []
    for i in range(int(n * 0.08)):
        t = i / SAMPLE_RATE
        v = _rng.uniform(-1.0, 1.0)
        if grit > 0.0:
            v = math.tanh(v * (1.0 + grit * 4.0))
        crack.append(v)
    crack = envelope_exp(highpass(crack, max(200.0, p["crack"] * 0.5)), p["body"] * 2.2)
    body = envelope_exp(lowpass(_noise(int(n * 0.8)), 900.0), p["body"])
    # 音高滑動的純音層（能量/雷射感）
    tonal = []
    if p["tonal"] > 0:
        m = int(n * 0.7)
        for i in range(m):
            t = i / SAMPLE_RATE
            f = p["tonal"] * (p["sweep"] ** (i / max(1, m)))
            tonal.append(0.35 * math.sin(math.tau * f * t))
        tonal = envelope_exp(tonal, 18.0)
    harmonic = []
    if p["tonal2"] > 0:
        m = int(n * 0.45)
        for i in range(m):
            t = i / SAMPLE_RATE
            f = p["tonal2"] * (p["sweep"] ** (i / max(1, m)))
            harmonic.append(0.16 * math.sin(math.tau * f * t))
        harmonic = envelope_exp(harmonic, 26.0)
    out = mix([s * 0.85 for s in crack], [s * 0.7 for s in body],
              [s * 0.5 for s in tonal], [s * 0.3 for s in harmonic])
    peak = max((abs(v) for v in out), default=1.0) or 1.0
    k = min(1.0, 0.95 / peak) * p["gain"]
    return [v * k for v in out]


def knife_swing() -> list[float]:
    """揮刀：短促呼嘯（帶通噪聲 + 快速滑音）。"""
    import math

    n = int(0.16 * SAMPLE_RATE)
    whoosh = envelope_exp(bandpass(_noise(n), 1400.0, 5200.0), 22.0)
    ring = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 2400.0 + 1800.0 * (i / n)
        ring[i] = 0.12 * math.sin(math.tau * f * t) * (1.0 - i / n)
    return mix(whoosh, ring)


def knife_hit() -> list[float]:
    """匕首命中：低沈濕音 + 金屬撞擊。"""
    thud = envelope_exp(lowpass(_noise(int(0.07 * SAMPLE_RATE)), 420.0), 34.0)
    tick = envelope_exp(highpass(_noise(int(0.02 * SAMPLE_RATE)), 3200.0), 700.0)
    return mix([s * 1.0 for s in thud], [s * 0.5 for s in tick])


def bandpass(x: list[float], low: float, high: float) -> list[float]:
    """极简带通：低通減去更低低通（够用，不引入外部 DSP 相依）。"""
    lo = lowpass(x, low)
    hi = lowpass(x, high)
    return [hi[i] - lo[i] for i in range(len(hi))]


# --------------------------------------------------------------------- #
# 註冊表：名稱 → 合成函式（CLI / 事件綁定共用）
# --------------------------------------------------------------------- #
SFX_REGISTRY: dict[str, callable] = {
    "gunshot_sidearm": lambda: gunshot("sidearm"),
    "gunshot_smg": lambda: gunshot("smg"),
    "gunshot_rifle": lambda: gunshot("rifle"),
    "gunshot_sniper": sniper_shot,
    "gunshot_shotgun": lambda: gunshot("shotgun"),
    "gunshot_heavy": lambda: gunshot("heavy"),
    "reload": reload,
    "mag_drop": mag_drop,
    "slide_rack": slide_rack,
    "empty_click": empty_click,
    "body_hit": body_hit,
    "headshot_confirm": headshot_confirm,
    "kill_confirm": lambda: kill_confirm(1),
    "multi_kill_2": lambda: multi_kill_announce(2),
    "multi_kill_3": lambda: multi_kill_announce(3),
    "multi_kill_4": lambda: multi_kill_announce(4),
    "damage_taken": damage_taken,
    "footstep": footstep,
    "landing": landing,
    "explosion": explosion,
    "ability_cast": ability_cast,
    "flash_explode": flash_explode,
    "smoke_puff": smoke_puff,
    "trap_trigger": trap_trigger,
    "concuss_effect": concuss_effect,
    "spike_beep": spike_beep,
    "spike_planted": spike_planted,
    "spike_defused": spike_defused,
    "spike_exploded": spike_exploded,
    "round_win": round_win,
    "round_loss": round_loss,
    "ui_click": ui_click,
    "ui_buy": ui_buy,
    "ui_error": ui_error,
    # 槍皮招牌音效（依 SKIN_SIGNATURES 自動註冊）
    "reaver_shot": (lambda s="reaver_shot": skin_shot(s)),
    "prime_shot": (lambda s="prime_shot": skin_shot(s)),
    "sentinels_shot": (lambda s="sentinels_shot": skin_shot(s)),
    "dragon_roar": (lambda s="dragon_roar": skin_shot(s)),
    "elderflame_shot": (lambda s="elderflame_shot": skin_shot(s)),
    "glitch_shot": (lambda s="glitch_shot": skin_shot(s)),
    "laser_shot": (lambda s="laser_shot": skin_shot(s)),
    "ice_shot": (lambda s="ice_shot": skin_shot(s)),
    "venom_shot": (lambda s="venom_shot": skin_shot(s)),
    "stardust_shot": (lambda s="stardust_shot": skin_shot(s)),
    "araxys_shot": (lambda s="araxys_shot": skin_shot(s)),
    "katana_swing": (lambda s="katana_swing": skin_shot(s)),
    "knife_swing": knife_swing,
    "knife_hit": knife_hit,
    # 終點球（新增鍵一律加在尾端：合成共用隨機流，插在中間會改到後面所有音效的位元組）
    "ult_ready_chime": ult_ready_chime,
    "ult_cast": ult_cast,
}
