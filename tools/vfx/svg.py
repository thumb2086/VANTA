"""
tools/vfx/svg.py — 程序化 SVG 貼圖產生器
========================================
以程式碼繪製遊戲用 2D 素材（粒子 sprite、HUD 圖示、準星、擊殺確認框），
輸出 SVG 文字檔（可再轉 PNG）。全部確定性、無第三方依賴。
"""

from __future__ import annotations

import os

SVG_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
)


def svg_document(w: int, h: int, elements: list[str]) -> str:
    return SVG_HEADER.format(w=w, h=h) + "\n".join(elements) + "\n</svg>\n"


def write_svg(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# --------------------------------------------------------------------- #
# 粒子 sprite（圓形漸層）
# --------------------------------------------------------------------- #
def sprite_circle(size: int, color: str, glow: bool = True, name: str = "sprite") -> str:
    """單一圓形粒子貼圖（可選光暈漸層）。"""
    r = size / 2
    elems = []
    if glow:
        elems.append(
            f'<radialGradient id="g"><stop offset="0%" stop-color="{color}" stop-opacity="0.9"/>'
            f'<stop offset="70%" stop-color="{color}" stop-opacity="0.35"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></radialGradient>'
        )
        elems.append(f'<circle cx="{r}" cy="{r}" r="{r}" fill="url(#g)"/>')
    else:
        elems.append(f'<circle cx="{r}" cy="{r}" r="{r}" fill="{color}"/>')
    return svg_document(size, size, elems)


def sprite_spark(size: int = 64) -> str:
    """火花：菱形四射。"""
    c = size / 2
    l = size * 0.3
    elems = [
        f'<g fill="#fff8d0">'
        f'<rect x="{c - l / 6}" y="{c - l}" width="{l / 3}" height="{l * 2}" rx="1"/>'
        f'<rect x="{c - l}" y="{c - l / 6}" width="{l * 2}" height="{l / 3}" rx="1"/>'
        f'</g>',
        f'<circle cx="{c}" cy="{c}" r="{size * 0.08}" fill="#fff"/>',
    ]
    return svg_document(size, size, elems)


def sprite_smoke(size: int = 96) -> str:
    """煙霧：多層半透明圓。"""
    elems = [
        f'<circle cx="{size * 0.5}" cy="{size * 0.55}" r="{size * 0.35}" fill="#9a9a9a" fill-opacity="0.35"/>',
        f'<circle cx="{size * 0.38}" cy="{size * 0.45}" r="{size * 0.25}" fill="#b0b0b0" fill-opacity="0.3"/>',
        f'<circle cx="{size * 0.62}" cy="{size * 0.48}" r="{size * 0.28}" fill="#8a8a8a" fill-opacity="0.3"/>',
        f'<circle cx="{size * 0.5}" cy="{size * 0.6}" r="{size * 0.3}" fill="#7a7a7a" fill-opacity="0.25"/>',
    ]
    return svg_document(size, size, elems)


def sprite_explosion(size: int = 128) -> str:
    """爆炸：中心亮核 + 橙色漸層。"""
    c = size / 2
    elems = [
        f'<radialGradient id="e"><stop offset="0%" stop-color="#fff" stop-opacity="0.95"/>'
        f'<stop offset="35%" stop-color="#ffd24a" stop-opacity="0.9"/>'
        f'<stop offset="75%" stop-color="#ff6a00" stop-opacity="0.6"/>'
        f'<stop offset="100%" stop-color="#c83000" stop-opacity="0"/></radialGradient>',
        f'<circle cx="{c}" cy="{c}" r="{size * 0.48}" fill="url(#e)"/>',
        *[f'<line x1="{c}" y1="{c}" x2="{c + size * 0.42 * math_cos(a)}" y2="{c + size * 0.42 * math_sin(a)}" '
          f'stroke="#ffdf80" stroke-width="3" stroke-linecap="round" opacity="0.8"/>'
          for a in (i * 0.785 for i in range(8))],
    ]
    return svg_document(size, size, elems)


def math_cos(a): return __import__("math").cos(a)
def math_sin(a): return __import__("math").sin(a)


# --------------------------------------------------------------------- #
# HUD 圖示
# --------------------------------------------------------------------- #
def hud_crosshair(size: int = 64, style: str = "classic") -> str:
    """準星（classic：四線 + 中心點；dot：單點）。"""
    c = size / 2
    if style == "dot":
        return svg_document(size, size, [f'<circle cx="{c}" cy="{c}" r="4" fill="#39ff14"/>'])
    gap = size * 0.1
    arm = size * 0.2
    w = 3
    color = "#39ff14"
    elems = [
        f'<rect x="{c - w / 2}" y="{c - gap - arm}" width="{w}" height="{arm}" fill="{color}"/>',
        f'<rect x="{c - w / 2}" y="{c + gap}" width="{w}" height="{arm}" fill="{color}"/>',
        f'<rect x="{c - gap - arm}" y="{c - w / 2}" width="{arm}" height="{w}" fill="{color}"/>',
        f'<rect x="{c + gap}" y="{c - w / 2}" width="{arm}" height="{w}" fill="{color}"/>',
        f'<circle cx="{c}" cy="{c}" r="2" fill="{color}"/>',
    ]
    return svg_document(size, size, elems)


def hud_kill_confirm(size: int = 128) -> str:
    """擊殺確認框（紅 X 標記）。"""
    c = size / 2
    l = size * 0.28
    return svg_document(size, size, [
        f'<g stroke="#ff3b3b" stroke-width="8" stroke-linecap="round">'
        f'<line x1="{c - l}" y1="{c - l}" x2="{c + l}" y2="{c + l}"/>'
        f'<line x1="{c + l}" y1="{c - l}" x2="{c - l}" y2="{c + l}"/>'
        f'</g>',
        f'<circle cx="{c}" cy="{c}" r="{size * 0.38}" fill="none" stroke="#ff3b3b" stroke-width="4" opacity="0.6"/>',
    ])


def hud_icon_ability(size: int = 64, glyph: str = "flash") -> str:
    """技能圖示占位（flash/frag/smoke/trap）。"""
    c = size / 2
    shapes = {
        "flash": f'<path d="M{c} {c - size * 0.3} l {size * 0.12} {size * 0.16} h {-size * 0.24} z" fill="#ffe066"/>'
                 f'<circle cx="{c}" cy="{c + size * 0.02}" r="6" fill="#fff"/>',
        "frag": f'<circle cx="{c}" cy="{c}" r="{size * 0.22}" fill="#8a8f98"/>'
                f'<circle cx="{c}" cy="{c}" r="{size * 0.08}" fill="#3a3d42"/>',
        "smoke": f'<circle cx="{c}" cy="{c}" r="{size * 0.2}" fill="#9a9a9a" fill-opacity="0.5"/>'
                 f'<circle cx="{c + size * 0.08}" cy="{c - size * 0.08}" r="{size * 0.14}" fill="#b0b0b0" fill-opacity="0.5"/>',
        "trap": f'<path d="M{c} {c - size * 0.25} v {size * 0.5} M{c - size * 0.25} {c} h {size * 0.5}" '
                f'stroke="#ffd24a" stroke-width="5" fill="none"/>',
    }
    return svg_document(size, size, [shapes.get(glyph, shapes["flash"])])


def hud_icon_spike(size: int = 64) -> str:
    """Spike 圖示。"""
    c = size / 2
    return svg_document(size, size, [
        f'<path d="M{c} {c - size * 0.28} v {size * 0.56} M{c - size * 0.28} {c} h {size * 0.56}" '
        f'stroke="#e23b3b" stroke-width="6" stroke-linecap="round" fill="none"/>',
    ])


VFX_SVG_REGISTRY: dict[str, callable] = {
    "sprite_spark": lambda p: sprite_spark(),
    "sprite_smoke": lambda p: sprite_smoke(),
    "sprite_explosion": lambda p: sprite_explosion(),
    "sprite_fire": lambda p: sprite_circle(64, "#ff8c1a"),
    "sprite_blood": lambda p: sprite_circle(48, "#b31212", glow=False),
    "hud_crosshair": lambda p: hud_crosshair(),
    "hud_kill_confirm": lambda p: hud_kill_confirm(),
    "hud_icon_flash": lambda p: hud_icon_ability(64, "flash"),
    "hud_icon_frag": lambda p: hud_icon_ability(64, "frag"),
    "hud_icon_smoke": lambda p: hud_icon_ability(64, "smoke"),
    "hud_icon_trap": lambda p: hud_icon_ability(64, "trap"),
    "hud_icon_spike": lambda p: hud_icon_spike(),
}
