"""
tools/fx/killfeed.py — 可程式化擊殺特效
=======================================
把「擊殺事件」轉為完整的特效序列：
  * KillEntry：擊殺紀錄（兇手/受害者/武器/爆頭/連殺/時間戳）
  * kill_feed 條目：HUD 擊殺訊息（含武器圖示、爆頭標記）
  * kill_confirm_sequence：擊殺確認動畫關鍵幀（十字線標記 → 粒子爆開 → 消退）
  * 連殺 (Multi-Kill) 宣告與遞升音效參數
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KillEntry:
    killer: str
    victim: str
    weapon: str
    headshot: bool = False
    streak: int = 1                # 兇手當前連殺數
    tick: int = 0
    team_kill: bool = False

    def to_feed(self) -> dict:
        """HUD 擊殺訊息（渲染層直接使用）。"""
        return {
            "killer": self.killer,
            "victim": self.victim,
            "weapon": self.weapon,
            "headshot": self.headshot,
            "streak": self.streak,
            "team_kill": self.team_kill,
            "icon": f"weapon_{self.weapon}",
            "headshot_icon": "headshot" if self.headshot else None,
        }


def kill_confirm_sequence(streak: int = 1, fps: int = 60, duration: float = 0.8) -> list[dict]:
    """擊殺確認動畫關鍵幀：中央 X 標記縮放/淡出 + 粒子指示。

    幀結構：[{t, scale, alpha, streak, particles: <vfx 引用>}] → 渲染層補間。
    """
    n = int(duration * fps)
    frames = []
    for i in range(n):
        t = i / fps
        u = t / duration
        # 出現 (0-15%) → 保持 (15-50%) → 淡出 (50-100%)
        if u < 0.15:
            scale = 0.6 + 0.4 * (u / 0.15)
            alpha = u / 0.15
        elif u < 0.5:
            scale, alpha = 1.0, 1.0
        else:
            fade = (u - 0.5) / 0.5
            scale = 1.0 + 0.1 * fade
            alpha = 1.0 - fade
        frames.append({
            "t": round(t, 3),
            "scale": round(scale, 3),
            "alpha": round(alpha, 3),
            "streak": streak,
            "particles": "kill_confirm" if u < 0.5 else None,
        })
    return frames


def multi_kill_thresholds() -> list[dict]:
    """連殺里程碑：名稱 + 所需連殺數 + 特效/音效引用。"""
    return [
        {"streak": 2, "name": "Double Kill", "sfx": "multi_kill_2"},
        {"streak": 3, "name": "Triple Kill", "sfx": "multi_kill_3"},
        {"streak": 4, "name": "Quadra Kill", "sfx": "multi_kill_4"},
        {"streak": 5, "name": "ACE!", "sfx": "multi_kill_4", "vfx": "ace"},
    ]


def multi_kill_label(streak: int) -> str | None:
    """依連殺數回傳里程碑名稱。"""
    name = None
    for m in multi_kill_thresholds():
        if streak >= m["streak"]:
            name = m["name"]
    return name


def kill_feed_entry(entry: KillEntry) -> dict:
    """擊殺事件 → 完整特效綁定（音效 + VFX + 訊息）。"""
    label = multi_kill_label(entry.streak)
    return {
        "feed": entry.to_feed(),
        "sfx": "headshot_confirm" if entry.headshot else "kill_confirm",
        "sfx_streak": f"multi_kill_{min(entry.streak, 4)}" if label else None,
        "vfx": "kill_confirm",
        "announce": label,
    }
