"""
tools/agents/portrait.py — 程序化角色肖像（SVG）
================================================
以角色定義（代號/定位/配色）繪製風格化頭像：
  * 背景：雙色漸層 + 科技感裝飾弧
  * 頭部：暗色面罩 + 發光護目鏡（依角色主色）
  * 肩甲：依強調色的幾何板塊
  * 定位圖騰：角落小圖示（flash/smoke/trap/spark）
輸出合法 SVG 文字檔（可轉 PNG / Godot 直接載入）。
完全確定性：只依賴角色定義欄位。
"""

from __future__ import annotations

import math

SVG_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
)


def portrait_svg(agent, size: int = 256) -> str:
    """agent 為 tools.agents.generator.AgentDef 或 dict（含 colors/role/stats）。"""
    if hasattr(agent, "to_dict"):
        d = agent.to_dict()
    else:
        d = agent
    c = d["colors"]
    role_glyph = d["stats"]["role_glyph"]
    codename = d["codename"]
    faction = d["faction"]
    s = float(size)
    c_ = s / 2.0

    elems = [
        # 背景漸層
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{c["bg1"]}"/>'
        f'<stop offset="100%" stop-color="{c["bg2"]}"/></linearGradient>'
        f'<radialGradient id="visor" cx="0.5" cy="0.5" r="0.5">'
        f'<stop offset="0%" stop-color="{c["accent"]}"/>'
        f'<stop offset="100%" stop-color="{c["primary"]}"/></radialGradient></defs>',
        f'<rect width="{s}" height="{s}" fill="url(#bg)"/>',
        # 科技裝飾弧（外圈）
        f'<circle cx="{c_}" cy="{c_}" r="{s * 0.46}" fill="none" stroke="{c["accent"]}" '
        f'stroke-width="1.5" opacity="0.35" stroke-dasharray="6 10"/>',
        f'<circle cx="{c_}" cy="{c_}" r="{s * 0.52}" fill="none" stroke="{c["primary"]}" '
        f'stroke-width="1" opacity="0.25"/>',
        # 肩甲（下方幾何）
        f'<path d="M0 {s} L{s * 0.12} {s * 0.78} L{s * 0.34} {s * 0.86} L{s * 0.44} {s} Z" '
        f'fill="{c["bg1"]}" stroke="{c["primary"]}" stroke-width="2"/>',
        f'<path d="M{s} {s} L{s * 0.88} {s * 0.78} L{s * 0.66} {s * 0.86} L{s * 0.56} {s} Z" '
        f'fill="{c["bg1"]}" stroke="{c["primary"]}" stroke-width="2"/>',
        # 頭部（暗色面罩）
        f'<ellipse cx="{c_}" cy="{s * 0.42}" rx="{s * 0.22}" ry="{s * 0.26}" '
        f'fill="#15181d" stroke="{c["primary"]}" stroke-width="2"/>',
        # 護目鏡（發光）
        f'<rect x="{c_ - s * 0.16}" y="{s * 0.36}" width="{s * 0.32}" height="{s * 0.09}" '
        f'rx="{s * 0.03}" fill="url(#visor)"/>',
        f'<rect x="{c_ - s * 0.11}" y="{s * 0.375}" width="{s * 0.07}" height="{s * 0.045}" '
        f'rx="2" fill="#0a0c10"/>',
        f'<rect x="{c_ + s * 0.04}" y="{s * 0.375}" width="{s * 0.07}" height="{s * 0.045}" '
        f'rx="2" fill="#0a0c10"/>',
        # 下頷通風口
        f'<line x1="{c_ - s * 0.08}" y1="{s * 0.58}" x2="{c_ + s * 0.08}" y2="{s * 0.58}" '
        f'stroke="{c["accent"]}" stroke-width="2" opacity="0.7"/>',
        # 頸部能量線
        f'<line x1="{c_}" y1="{s * 0.62}" x2="{c_}" y2="{s * 0.76}" '
        f'stroke="{c["accent"]}" stroke-width="3" opacity="0.8"/>',
        # 定位圖騰（右上）
        *_role_glyph(c_, s, role_glyph, c["accent"]),
        # 代號條（底部）
        f'<rect x="{s * 0.08}" y="{s * 0.9}" width="{s * 0.84}" height="{s * 0.06}" rx="3" '
        f'fill="{c["primary"]}" opacity="0.85"/>',
        f'<text x="{c_}" y="{s * 0.952}" text-anchor="middle" '
        f'font-size="{s * 0.055}" fill="#ffffff" font-family="sans-serif" font-weight="bold">'
        f'{codename} · {faction}</text>',
    ]
    return SVG_HEADER.format(w=size, h=size) + "\n".join(elems) + "\n</svg>\n"


def _role_glyph(cx: float, s: float, glyph: str, color: str) -> list[str]:
    """角落定位圖騰。"""
    gx = cx + s * 0.36
    gy = s * 0.18
    k = s / 64.0
    shapes = {
        "flash": (f'<path d="M{gx} {gy - 8 * k} l {6 * k} {9 * k} h {-12 * k} z" fill="{color}"/>'
                  f'<circle cx="{gx}" cy="{gy + 1 * k}" r="{3 * k}" fill="#fff"/>'),
        "smoke": (f'<circle cx="{gx}" cy="{gy}" r="{10 * k}" fill="{color}" fill-opacity="0.5"/>'
                  f'<circle cx="{gx + 4 * k}" cy="{gy - 4 * k}" r="{7 * k}" fill="{color}" fill-opacity="0.5"/>'),
        "trap": (f'<path d="M{gx} {gy - 12 * k} v {24 * k} M{gx - 12 * k} {gy} h {24 * k}" '
                 f'stroke="{color}" stroke-width="{4 * k}" fill="none"/>'),
        "spark": (f'<circle cx="{gx}" cy="{gy}" r="{10 * k}" fill="none" stroke="{color}" '
                  f'stroke-width="{2 * k}"/>'
                  f'<circle cx="{gx}" cy="{gy}" r="{3 * k}" fill="{color}"/>'),
    }
    return [shapes.get(glyph, shapes["flash"])]


def write_portrait(path: str, agent) -> None:
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(portrait_svg(agent))
