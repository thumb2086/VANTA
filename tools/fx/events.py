"""
tools/fx/events.py — 遊戲事件 → 特效綁定表
==========================================
統一的「事件 → (音效, VFX, HUD 回饋)」對照，確保每個遊戲事件都有
可程式化的表現層回應（與 server.game 的事件名對齊）。
"""

from __future__ import annotations

# 事件 → {sfx, vfx, feed, announce}
EVENT_FX: dict[str, dict] = {
    # 戰鬥
    "kill": {"sfx": "kill_confirm", "vfx": "kill_confirm", "feed": True},
    "headshot": {"sfx": "headshot_confirm", "vfx": "kill_confirm", "feed": True},
    "multi_kill": {"sfx": "multi_kill_2", "vfx": "kill_confirm", "announce": True},
    "damage_taken": {"sfx": "damage_taken", "vfx": "hit_marker_inverse"},
    "hit_confirm": {"sfx": "body_hit", "vfx": "hit_marker"},
    # 武器
    "reload": {"sfx": "reload"},
    "empty_click": {"sfx": "empty_click"},
    "footstep": {"sfx": "footstep"},
    "landing": {"sfx": "landing"},
    # 技能
    "ability_cast": {"sfx": "ability_cast"},
    "flash_explode": {"sfx": "flash_explode", "vfx": "flash_burst"},
    "smoke_spawn": {"sfx": "smoke_puff", "vfx": "smoke_puff"},
    "trap_trigger": {"sfx": "trap_trigger", "vfx": "trap_trigger"},
    "concussed": {"sfx": "concuss_effect", "vfx": "screen_ring"},
    "blinded": {"sfx": "flash_explode", "vfx": "screen_white"},
    # Spike
    "spike_beep": {"sfx": "spike_beep"},
    "spike_planting": {"sfx": "ability_cast"},
    "spike_planted": {"sfx": "spike_planted", "vfx": "spike_icon_pulse", "feed": True},
    "spike_defusing": {"sfx": "ability_cast"},
    "spike_defused": {"sfx": "spike_defused", "vfx": "spike_icon_clear", "feed": True},
    "spike_detonated": {"sfx": "spike_exploded", "vfx": "explosion_debris", "feed": True},
    # 回合 / 系統
    "round_win": {"sfx": "round_win", "vfx": "round_banner_win"},
    "round_loss": {"sfx": "round_loss", "vfx": "round_banner_loss"},
    "buy_success": {"sfx": "ui_buy"},
    "buy_failed": {"sfx": "ui_error"},
    "ui_click": {"sfx": "ui_click"},
}


# 螢幕/介面特效（渲染層實作；粒子與 SVG 之外的第三類 VFX）
SCREEN_VFX: set[str] = {
    "hit_marker_inverse", "flash_burst", "trap_trigger",
    "screen_ring", "screen_white",
    "spike_icon_pulse", "spike_icon_clear",
    "round_banner_win", "round_banner_loss",
}


def fx_for(event: str) -> dict | None:
    """查詢事件的特效綁定。未知事件回 None（可程式化擴充）。"""
    return EVENT_FX.get(event)


def all_events() -> list[str]:
    """列出所有已綁定的事件。"""
    return sorted(EVENT_FX)


def validate_bindings(sfx_registry: set[str], vfx_registry: set[str]) -> list[str]:
    """驗證綁定表引用的音效/VFX 都存在（VFX 含粒子、SVG 與螢幕特效）。"""
    valid_vfx = set(vfx_registry) | SCREEN_VFX
    issues = []
    for event, fx in EVENT_FX.items():
        if "sfx" in fx and fx["sfx"] not in sfx_registry:
            issues.append(f"{event}: 音效 '{fx['sfx']}' 不存在")
        if "vfx" in fx and fx["vfx"] not in valid_vfx:
            issues.append(f"{event}: VFX '{fx['vfx']}' 不存在")
    return issues
