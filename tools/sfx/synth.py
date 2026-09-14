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
}
