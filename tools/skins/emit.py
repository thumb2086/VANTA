"""
tools/skins/emit.py — 槍皮素材輸出（JSON / 預覽卡 / 程序化貼圖）
=============================================================
輸出項目：
  * `skins.json`  —— 完整目錄（Godot SkinRegistry 與展示台共用）
  * `cards/<coll>.svg` —— 系列卡片（商店/軍械庫介面用）
  * `textures/<coll>_<colorway>_{albedo,emissive,normal,orm}.png` —— 選用
    （客戶端預設「依參數即時生成」，因此 PNG 只是給 Blender/網頁離線版用；
     預設不產生，避免倉庫塞入幾 MB 的二進位檔。）
"""

from __future__ import annotations

import math
import os

from tools.skins import patterns
from tools.skins.catalog import TIERS, collect, hex_to_rgb, mix, shade
from tools.skins.png import write_png

TEXTURE_SIZE = 256

# 貼圖合成規格（Godot / 網頁展示台必須使用同一組常數，才能跨平台一致）
TEX = {
    "version": 2,
    "detail_weight": 0.20,          # 高頻細節混入比（只影響 albedo/法線，不影響發光位置）
    "detail_scale": 7.0,
    "smooth_passes": 1,             # 花紋本身先柔一次（去掉階梯感）
    "edge_blur": 2,                 # 求梯度前先模糊：只保留「結構」邊緣
    "edge_stride": 1,               # 中心差分步長（像素）
    "edge_gain": 1.15,              # 相對強度（搭配 edge_normalize 後與花紋無關）
    "edge_normalize": 1,            # 1 = 以 90 分位數正規化 → 各花紋發光強度可比
    "emissive_gain": 0.34,
    "emissive_ridge_threshold": 0.78,
    "emissive_ridge_weight": 0.18,  # 高亮頂面額外補一點光（不可超过脊線）
    "emissive_curve": 1.35,         # >1 → 壓掉中間值，讓光「聚在線上」
    "albedo_shade_min": 0.62,       # 凹凸明暗範圍
    "albedo_shade_range": 0.52,
    "normal_strength": 2.2,
    "ao_base": 0.5,
    "roughness_pattern_gain": 0.26,
    "metal_pattern_gain": 0.10,
}


# --------------------------------------------------------------------- #
# 紋理合成
# --------------------------------------------------------------------- #
def _hex_rgb(color: str) -> tuple:
    return hex_to_rgb(color)


def _params_with_seed(params: dict | None, seed: int) -> dict:
    """花紋參數＋確定性 seed（未指定時用呼叫端 seed）。"""
    out = dict(params or {})
    out.setdefault("seed", int(seed))
    return out


def _smooth_grid(grid: list[list[float]], passes: int = 1) -> list[list[float]]:
    """輕度模糊：抹除噪訊的階梯感，讓法線與發光邊緣更柔。"""
    size = len(grid)
    g = grid
    for _ in range(max(0, passes)):
        ng = [[0.0] * size for _ in range(size)]
        for y in range(size):
            ym, yp = (y - 1) % size, (y + 1) % size
            row, rowm, rowp = g[y], g[ym], g[yp]
            for x in range(size):
                xm, xp = (x - 1) % size, (x + 1) % size
                ng[y][x] = (row[x] * 4.0 + row[xm] + row[xp] + rowm[x] + rowp[x]) / 8.0
        g = ng
    return g


def _edge_field(struct: list[list[float]]) -> list[list[float]]:
    """結構脊線場：先模糊（去掉細節）→ 中心差分 → 以 90 分位數正規化。

    正規化的理由：不同花紋的「天然對比」差很多（hex 的格線 vs marble 的流紋），
    若直接用絕對梯度，某些花紋會整片飽和、某些幾乎不發光。以分位數縮放之後，
    「光只沿最銳利的線走」這條規則對 14 種花紋都成立。
    """
    size = len(struct)
    blur = _smooth_grid(struct, int(TEX["edge_blur"]))
    stride = max(1, int(TEX["edge_stride"]))
    raw: list[list[float]] = []
    flat: list[float] = []
    for y in range(size):
        yp = (y + stride) % size
        ym = (y - stride) % size
        row: list[float] = []
        for x in range(size):
            xp = (x + stride) % size
            xm = (x - stride) % size
            dx = blur[y][xp] - blur[y][xm]
            dy = blur[yp][x] - blur[ym][x]
            v = math.sqrt(dx * dx + dy * dy)
            row.append(v)
            flat.append(v)
        raw.append(row)
    if int(TEX.get("edge_normalize", 1)) and flat:
        flat.sort()
        ref = flat[min(len(flat) - 1, int(len(flat) * 0.90))]
    else:
        ref = 1.0
    ref = max(ref, 1e-4)
    gain = float(TEX["edge_gain"])
    return [[min(1.0, raw[y][x] / ref * gain) for x in range(size)] for y in range(size)]


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _gradient(grid: list[list[float]], x: int, y: int) -> tuple:
    size = len(grid)
    dx = grid[y][(x + 1) % size] - grid[y][(x - 1) % size]
    dy = grid[(y + 1) % size][x] - grid[(y - 1) % size][x]
    return dx, dy


def compose_maps(pattern: str, params: dict, colorway: dict, size: int = TEXTURE_SIZE,
                 seed: int = 0) -> dict[str, bytes]:
    """依「花紋 + 色板」合成四張貼圖。

    回傳 {"albedo": RGBA, "emissive": RGB, "normal": RGB, "orm": RGB}
    （皆為 row-major bytes，交由 png 模組編碼）

    品質關鍵（也是 Godot/展示台實作需對齊的規格）：
      1. 花紋經平滑＋高頻細節疊加 → 不會出現大色塊。
      2. 發光只沿「花紋脊線／邊緣」→ 有质感的高級皮，而不是整片自體發光。
      3. 凹陷處變暗（AO）、凸面更亮更光滑（roughness 隨高度變化）。
      4. 磨損：高磨损時邊緣露出底材金属色。
    """
    # 「結構層」與「細節層」分開處理，這是品質的關鍵：
    # 發光必須沿花紋本身的脊線（結構），若把高頻細節也算進邊緣，
    # 整張圖會變成一片燈箱（實測：cracks 91% 像素飽和 → 明顯劣化）。
    struct = _smooth_grid(patterns.render(pattern, size, _params_with_seed(params, seed)))
    detail = patterns.render("noise", size, {"scale": float(TEX["detail_scale"]),
                                             "contrast": 1.15, "octaves": 4,
                                             "seed": seed + 41})
    dw = float(TEX["detail_weight"])
    grid = [[min(1.0, max(0.0, struct[y][x] * (1.0 - dw) + detail[y][x] * dw))
              for x in range(size)] for y in range(size)]
    edge_grid = _edge_field(struct)                              # 結構脊線（相對強度正規化）
    wear_grid = patterns.render("noise", size, {"scale": 4.5, "contrast": 1.5,
                                                "seed": seed + 91})

    primary = hex_to_rgb(colorway.get("primary", "#2b2f38"))
    secondary = hex_to_rgb(colorway.get("secondary", "#171a20"))
    accent = hex_to_rgb(colorway.get("accent", "#ff7a35"))
    emissive_c = hex_to_rgb(colorway.get("emissive", "#ff9d4d"))
    rim = hex_to_rgb(colorway.get("rim_color", "#ffffff"))

    mix_amt = float(colorway.get("pattern_mix", 0.45))
    emis_gain = float(colorway.get("emissive_strength", 1.0))
    wear = float(colorway.get("wear", 0.12))
    rough = float(colorway.get("roughness", 0.38))
    metal = float(colorway.get("metalness", 0.55))
    irid = float(colorway.get("iridescence", 0.0))

    albedo = bytearray(size * size * 4)
    emis = bytearray(size * size * 3)
    orm = bytearray(size * size * 3)

    for y in range(size):
        grow = grid[y]
        wrow = wear_grid[y]
        for x in range(size):
            g = grow[x]
            i = y * size + x
            dx, dy = _gradient(grid, x, y)
            micro = min(1.0, math.hypot(dx, dy) * 6.0)
            # 發光位置由「結構脊線」決定；細節只讓它有些許顆粒感
            edge = min(1.0, edge_grid[y][x] * (0.90 + 0.10 * micro))

            # ── albedo ──
            base = mix(primary, secondary, _smoothstep(g) * mix_amt)
            base = mix(base, accent, edge * (0.30 + 0.40 * mix_amt))
            base = shade(base, float(TEX["albedo_shade_min"]) + TEX["albedo_shade_range"] * g)
            wear_mask = min(1.0, max(0.0, (wrow[x] - (1.0 - wear)) / max(0.05, wear)))
            if wear_mask > 0.0:
                base = mix(base, mix(shade(base, 1.45), (148, 150, 158), 0.55),
                           wear_mask * 0.5)
            if irid > 0.0:
                hue = (x / size + y / size) * math.tau
                tint = tuple(int(255 * (0.5 + 0.5 * math.sin(hue + k * 2.09))) for k in range(3))
                base = mix(base, tint, irid * 0.32)
            albedo[i * 4] = base[0]
            albedo[i * 4 + 1] = base[1]
            albedo[i * 4 + 2] = base[2]
            albedo[i * 4 + 3] = 255

            # ── emission：以「脊線」為主、凸起頂部為輔（避免整片糊成燈箱）──
            ridge = max(0.0, g - float(TEX["emissive_ridge_threshold"])) / (
                1.0 - float(TEX["emissive_ridge_threshold"]))
            raw = (edge + float(TEX["emissive_ridge_weight"]) * ridge * ridge) \
                * emis_gain * float(TEX["emissive_gain"])
            em = min(1.0, raw) ** float(TEX["emissive_curve"])
            e_col = mix(emissive_c, rim, 0.30 * (1.0 - em))
            emis[i * 3] = min(255, int(e_col[0] * em))
            emis[i * 3 + 1] = min(255, int(e_col[1] * em))
            emis[i * 3 + 2] = min(255, int(e_col[2] * em))

            # ── ORM：R=AO G=粗糙度 B=金屬度 ──
            orm[i * 3] = int(255 * min(1.0, TEX["ao_base"] + (1.0 - TEX["ao_base"]) * g))
            orm[i * 3 + 1] = int(255 * max(0.0, min(1.0, rough + (0.5 - g)
                                                     * TEX["roughness_pattern_gain"] - edge * 0.12)))
            orm[i * 3 + 2] = int(255 * max(0.0, min(1.0, metal + edge
                                                     * TEX["metal_pattern_gain"] + wear_mask * 0.30)))

    normal_grid = patterns.height_to_normal(grid, strength=float(TEX["normal_strength"]))
    normal = bytearray(size * size * 3)
    for y in range(size):
        for x in range(size):
            nx, ny, nz = normal_grid[y][x]
            i = (y * size + x) * 3
            normal[i] = int((nx * 0.5 + 0.5) * 255)
            normal[i + 1] = int((ny * 0.5 + 0.5) * 255)
            normal[i + 2] = int((nz * 0.5 + 0.5) * 255)
    return {"albedo": bytes(albedo), "emissive": bytes(emis),
            "normal": bytes(normal), "orm": bytes(orm)}


def _smoothstep(v: float) -> float:
    v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
    return v * v * (3.0 - 2.0 * v)


def texture_spec() -> dict:
    """外露給渲染層的規格常數（寫進 skins.json，確保三方一致）。"""
    return dict(TEX)


def write_skin_textures(coll_id: str, colorway: dict, pattern: str, params: dict,
                        out_dir: str, size: int = TEXTURE_SIZE) -> list[str]:
    maps = compose_maps(pattern, params, colorway, size)
    written: list[str] = []
    for name in ("albedo", "emissive", "normal", "orm"):
        channels = 4 if name == "albedo" else 3
        path = os.path.join(out_dir, f"{coll_id}_{name}.png")
        write_png(path, size, size, maps[name], channels)
        written.append(path)
    return written


# --------------------------------------------------------------------- #
# 系列卡片（SVG）
# --------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def collection_card(coll: dict, skins: list[dict], w: int = 480, h: int = 270) -> str:
    """繪製一張系列卡：漸層背景 + 階級色 + 武器條 + 文案。"""
    tier_color = TIERS[coll["tier"]]["color"]
    cw = (skins[0]["colorway"] if skins else {})
    primary = cw.get("primary", "#1b1e26")
    accent = cw.get("accent", tier_color)
    emissive = cw.get("emissive", accent)
    bars = []
    n = max(1, len(skins))
    for i, sk in enumerate(skins[:10]):
        bx = 28 + i * (w - 56) / n
        bars.append(
            f'<rect x="{bx:.1f}" y="{h - 74:.1f}" width="{(w - 56) / n - 4:.1f}" height="26" '
            f'rx="3" fill="{sk["colorway"]["primary"]}" stroke="{sk["colorway"]["accent"]}" '
            f'stroke-width="1" opacity="0.95"/>'
            f'<rect x="{bx:.1f}" y="{h - 46:.1f}" width="{(w - 56) / n - 4:.1f}" height="4" '
            f'rx="2" fill="{sk["tier_color"]}"/>'
        )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{primary}"/>
      <stop offset="60%" stop-color="#0a0c12"/>
      <stop offset="100%" stop-color="{coll.get("tier_color", tier_color)}" stop-opacity="0.35"/>
    </linearGradient>
    <radialGradient id="glow" cx="70%" cy="30%" r="60%">
      <stop offset="0%" stop-color="{emissive}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{emissive}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg)"/>
  <rect width="{w}" height="{h}" fill="url(#glow)"/>
  <rect x="0" y="0" width="{w}" height="4" fill="{tier_color}"/>
  <text x="28" y="58" font-family="sans-serif" font-size="30" font-weight="700"
        fill="#f2f4f8">{_esc(coll["name"])}</text>
  <text x="28" y="82" font-family="sans-serif" font-size="14" letter-spacing="3"
        fill="{accent}">{_esc(coll["name_en"].upper())}</text>
  <text x="28" y="112" font-family="sans-serif" font-size="12" fill="#9aa2b2">{_esc(coll["tier_label"])} ｜ {n} 把武器</text>
  <text x="28" y="140" font-family="sans-serif" font-size="12" fill="#c3cad8" opacity="0.85">{_esc(coll["lore"][:44])}</text>
  {''.join(bars)}
  <text x="28" y="{h - 12}" font-family="sans-serif" font-size="11" fill="#6f7889">
    {_esc(coll["artist"])} ・ {_esc(coll["release"])} ・ {coll["price_vp"]} VP
  </text>
</svg>
'''


# --------------------------------------------------------------------- #
# 主輸出
# --------------------------------------------------------------------- #
def emit(out_root: str, textures: bool = False, texture_size: int = TEXTURE_SIZE,
          texture_collections: list[str] | None = None) -> dict:
    """產生 assets/skins/*，回傳寫入統計。"""
    from tools.schema import write_json

    os.makedirs(out_root, exist_ok=True)
    data = collect()
    catalog_path = os.path.join(out_root, "skins.json")
    write_json(catalog_path, data)

    cards_dir = os.path.join(out_root, "cards")
    os.makedirs(cards_dir, exist_ok=True)
    by_coll: dict[str, list] = {}
    for sk in data["skins"]:
        by_coll.setdefault(sk["collection"], []).append(sk)
    card_files = []
    for coll in data["collections"]:
        svg = collection_card(coll, by_coll.get(coll["id"], []))
        path = os.path.join(cards_dir, f"{coll['id']}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        card_files.append(path)

    tex_files: list[str] = []
    if textures:
        tex_dir = os.path.join(out_root, "textures")
        os.makedirs(tex_dir, exist_ok=True)
        wanted = set(texture_collections) if texture_collections else set(by_coll)
        for coll_id, skins in sorted(by_coll.items()):
            if coll_id not in wanted or not skins:
                continue
            sk = skins[0]
            written = write_skin_textures(coll_id, sk["colorway"], sk["pattern"],
                                          sk["pattern_params"], tex_dir, texture_size)
            tex_files.extend(written)
            for cw in sk.get("chroma", []):
                written = write_skin_textures(f"{coll_id}_{cw['name']}", cw, sk["pattern"],
                                              sk["pattern_params"], tex_dir, texture_size)
                tex_files.extend(written)

    return {"catalog": catalog_path, "cards": card_files, "textures": tex_files,
            "skins": len(data["skins"]), "collections": len(data["collections"])}
