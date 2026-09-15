"""
tools/skins/patterns.py — 程序化花紋（Gun skin pattern generators）
=================================================================
所有函式回傳 `size*size` 的 float 灰階網格（0..1），可用於：
  * albedo 色相調變（把 0..1 當 mix 權重）
  * emission 遮罩（0..1 當發光強度）
  * height → normal map（Sobel 差分）

同一份實作被 Godot（`client/scripts/procedural_texture.gd`）與網頁展示台
（`showcase/`）以相同常數重写，作為「跨平台紋理一致性」的依據。
"""

from __future__ import annotations

import math

# 全域常數：跨語言/跨平台必須一致
TILE = 8                    # 值噪訊的整數平鋪格數（保证可 seamless 平铺）
OCTAVES = 4                 # fBm 疊加層數
GAIN = 0.5                  # fBm 振幅衰減


# --------------------------------------------------------------------- #
# 雜湊與值噪訊
# --------------------------------------------------------------------- #
def hash2(ix: int, iy: int, seed: int = 0) -> float:
    """整數格點偽隨機值（0..1），週期 2^31；與 Godot/JS 實作逐位元組一致。"""
    n = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) & 0xFFFFFFFF
    n = (n * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967295.0


def _smooth(t: float) -> float:
    """Hermite（3t^2-2t^3）平滑曲線。"""
    return t * t * (3.0 - 2.0 * t)


def value_noise(x: float, y: float, seed: int = 0, tile: int = TILE) -> float:
    """可平鋪（tiling）值噪訊。x/y 以「格」為單位。"""
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    fx = _smooth(x - x0)
    fy = _smooth(y - y0)
    m = tile if tile > 0 else (1 << 30)
    x0m, x1m = x0 % m, (x0 + 1) % m
    y0m, y1m = y0 % m, (y0 + 1) % m
    v00 = hash2(x0m, y0m, seed)
    v10 = hash2(x1m, y0m, seed)
    v01 = hash2(x0m, y1m, seed)
    v11 = hash2(x1m, y1m, seed)
    a = v00 + (v10 - v00) * fx
    b = v01 + (v11 - v01) * fx
    return a + (b - a) * fy


def fbm(x: float, y: float, seed: int = 0, octaves: int = OCTAVES,
        lacunarity: float = 2.0, gain: float = GAIN, tile: int = TILE) -> float:
    """分形噪訊（多倍頻疊加），回傳 0..1。"""
    amp = 0.5
    total = 0.0
    norm = 0.0
    freq = 1.0
    for o in range(octaves):
        t = tile * int(lacunarity ** o) if tile > 0 else 0
        total += amp * value_noise(x * freq, y * freq, seed + o * 977, t)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm if norm else 0.0


def ridged(x: float, y: float, seed: int = 0, octaves: int = OCTAVES, tile: int = TILE) -> float:
    """脊狀噪訊（1-|2n-1|）：適合裂縫 / 山脈 / 火焰紋。"""
    amp = 0.5
    total = 0.0
    norm = 0.0
    freq = 1.0
    for o in range(octaves):
        t = tile * int(lacunarity_pow(freq)) if tile > 0 else 0
        n = value_noise(x * freq, y * freq, seed + o * 541, t)
        r = 1.0 - abs(n * 2.0 - 1.0)
        total += amp * r * r
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm if norm else 0.0


def lacunarity_pow(freq: float) -> int:
    """把倍頻頻率換成整數平鋪倍數（保持無縫）。"""
    return max(1, int(round(freq)))


# --------------------------------------------------------------------- #
# 花紋產生器（每個回傳 size*size 的 list[list[float]]）
# --------------------------------------------------------------------- #
def _grid(size: int, fn) -> list[list[float]]:
    return [[fn(x, y) for x in range(size)] for y in range(size)]


def pat_solid(size: int, params: dict) -> list[list[float]]:
    v = float(params.get("value", 0.5))
    return [[v] * size for _ in range(size)]


def pat_noise(size: int, params: dict) -> list[list[float]]:
    """細顆粒磨砂 / 磨損。"""
    scale = float(params.get("scale", 3.0))
    seed = int(params.get("seed", 0))
    contrast = float(params.get("contrast", 1.0))
    oct_ = int(params.get("octaves", 3))

    def f(x: int, y: int) -> float:
        n = fbm(x / size * TILE * scale, y / size * TILE * scale, seed, oct_, tile=TILE)
        return _contrast(n, contrast)

    return _grid(size, f)


def pat_marble(size: int, params: dict) -> list[list[float]]:
    """流紋 / 大理石（生物材質、龍鱗底紋）。"""
    scale = float(params.get("scale", 2.0))
    seed = int(params.get("seed", 1))
    twist = float(params.get("twist", 6.0))

    def f(x: int, y: int) -> float:
        u = x / size * math.tau * scale
        v = y / size * math.tau * scale
        n = fbm(x / size * TILE * scale, y / size * TILE * scale, seed, 4, tile=TILE)
        s = math.sin(u + v + twist * n)
        return _clamp01(0.5 + 0.5 * s)

    return _grid(size, f)


def pat_scales(size: int, params: dict) -> list[list[float]]:
    """龍鱗 / 蛇鱗：錯位胞格，每鱗有球面高光，隙縫變暗。"""
    cells = int(params.get("cells", 10))
    seed = int(params.get("seed", 3))
    bump = float(params.get("bump", 1.0))

    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        for x in range(size):
            gy = y / size * cells
            gx = x / size * cells + (0.5 if int(gy) % 2 else 0.0)
            cx = math.floor(gx)
            cy = math.floor(gy)
            fx = gx - cx
            fy = gy - cy
            d = math.hypot(fx - 0.5, fy - 0.5)
            dome = _clamp01(1.0 - d * 2.0)                       # 鱗面隆起
            v = 0.20 + 0.66 * (dome ** 0.55) + 0.14 * hash2(cx, cy, seed)
            gap = _clamp01((d - 0.42) * 6.0)                     # 鱗片間隙
            v *= 1.0 - bump * gap * 0.85
            row.append(_clamp01(v))
        out.append(row)
    return out


def pat_hex(size: int, params: dict) -> list[list[float]]:
    """六角科技格（Ion / Sentinel 風格的發光格線）。

    六角格 = 三組平行線族的聯集；到最近的「格線」距離即邊界強度，
    如此可得到無縫且完全確定的六邊形網路。
    """
    cells = int(params.get("cells", 8))
    glow = float(params.get("glow", 0.22))
    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        v = y / size * cells
        for x in range(size):
            u = x / size * cells * 1.1547          # 2/sqrt(3)
            d1 = abs(((u + v) % 1.0) - 0.5)
            d2 = abs(((u - v) % 1.0) - 0.5)
            d3 = abs((v % 1.0) - 0.5)
            edge = max(d1, d2, d3) * 2.0            # 0=格線中心, 1=胞內
            row.append(_clamp01(1.0 - _clamp01(edge / max(0.01, glow))))
        out.append(row)
    return out


def pat_scanline(size: int, params: dict) -> list[list[float]]:
    """水平掃描線 + 隨機位移（Glitchpop 故障感）。"""
    lines = int(params.get("lines", 40))
    blocky = float(params.get("blocky", 0.5))
    seed = int(params.get("seed", 7))
    out: list[list[float]] = []
    for y in range(size):
        band = math.sin(y / size * lines * math.tau) * 0.5 + 0.5
        block_row = hash2(0, y // max(1, size // 16), seed)
        shift = 0.0
        if block_row > 1.0 - blocky * 0.35:
            shift = (hash2(y, 7, seed) - 0.5) * 0.8
        row: list[float] = []
        for x in range(size):
            v = band + shift
            row.append(_clamp01(v))
        out.append(row)
    return out


def pat_circuit(size: int, params: dict) -> list[list[float]]:
    """電路走線（雷電 / 機甲風格）：格線 + 節點亮點。"""
    cells = int(params.get("cells", 12))
    seed = int(params.get("seed", 11))
    width = float(params.get("width", 0.16))
    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        gy = y / size * cells
        iy = math.floor(gy)
        fy = gy - iy
        for x in range(size):
            gx = x / size * cells
            ix = math.floor(gx)
            fx = gx - ix
            r = hash2(ix, iy, seed)
            line = 0.0
            if r < 0.5:
                line = max(line, 1.0 - _clamp01(abs(fy - 0.5) / width))
            else:
                line = max(line, 1.0 - _clamp01(abs(fx - 0.5) / width))
            if r > 0.78:      # 節點
                line = max(line, 1.0 - _clamp01(math.hypot(fx - 0.5, fy - 0.5) / (width * 1.6)))
            row.append(_clamp01(line))
        out.append(row)
    return out


def pat_cracks(size: int, params: dict) -> list[list[float]]:
    """裂縫 / 熔岩紋（Reaver、Elderflame）：脊狀噪訊求逆。"""
    scale = float(params.get("scale", 3.0))
    seed = int(params.get("seed", 13))
    sharp = float(params.get("sharp", 3.0))
    glow = float(params.get("glow", 0.55))

    def f(x: int, y: int) -> float:
        r = ridged(x / size * TILE * scale, y / size * TILE * scale, seed, 4, tile=TILE)
        c = _clamp01(1.0 - r) ** sharp
        return _clamp01(c * (1.0 + glow * 2.0))

    return _grid(size, f)


def pat_frost(size: int, params: dict) -> list[list[float]]:
    """冰霜結晶：Voronoi 邊界 + 霧面。"""
    cells = int(params.get("cells", 9))
    seed = int(params.get("seed", 17))
    pts = []
    n = cells * cells
    for i in range(n):
        ix = i % cells
        iy = i // cells
        pts.append(((ix + hash2(ix, iy, seed)) / cells, (iy + hash2(ix, iy, seed + 3)) / cells))
    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        v = y / size
        for x in range(size):
            u = x / size
            d1 = 9.9
            d2 = 9.9
            for (px, py) in pts:
                dx = u - px
                dy = v - py
                if dx > 0.5:
                    dx -= 1.0
                if dx < -0.5:
                    dx += 1.0
                if dy > 0.5:
                    dy -= 1.0
                if dy < -0.5:
                    dy += 1.0
                dd = dx * dx + dy * dy
                if dd < d1:
                    d2 = d1
                    d1 = dd
                elif dd < d2:
                    d2 = dd
            edge = _clamp01(1.0 - (math.sqrt(d2) - math.sqrt(d1)) * cells * 1.4)
            row.append(_clamp01(0.18 + 0.82 * edge))
        out.append(row)
    return out


def pat_nebula(size: int, params: dict) -> list[list[float]]:
    """星雲 + 星點（Nova / Cosmos）。"""
    seed = int(params.get("seed", 23))
    stars = int(params.get("stars", 60))
    scale = float(params.get("scale", 2.0))
    star_pts = [(hash2(i, 1, seed), hash2(i, 2, seed + 1)) for i in range(stars)]
    star_sz = float(params.get("star_size", 0.010))

    def f(x: int, y: int) -> float:
        u = x / size
        v = y / size
        n = fbm(u * TILE * scale, v * TILE * scale, seed, 5, tile=TILE)
        core = n ** 2.2
        s = 0.0
        for (sx, sy) in star_pts:
            du = abs(u - sx)
            dv = abs(v - sy)
            d = math.hypot(min(du, 1.0 - du), min(dv, 1.0 - dv))
            if d < star_sz * 6:
                s = max(s, _clamp01(1.0 - d / star_sz))
        return _clamp01(core * 0.8 + s)

    return _grid(size, f)


def pat_flame(size: int, params: dict) -> list[list[float]]:
    """流動火焰（呼吸感）：垂直漸層 + 擾動。"""
    seed = int(params.get("seed", 29))
    freq = float(params.get("freq", 3.0))

    def f(x: int, y: int) -> float:
        u = x / size
        v = y / size
        n = fbm(u * TILE * freq, v * TILE * freq, seed, 4, tile=TILE)
        ramp = _clamp01(1.0 - v)
        return _clamp01(ramp * (0.45 + 1.4 * n))

    return _grid(size, f)


def pat_camo(size: int, params: dict) -> list[list[float]]:
    """迷彩斑塊（軍規 / 戰術風格）。"""
    seed = int(params.get("seed", 31))
    blobs = int(params.get("blobs", 14))
    centers = [(hash2(i, 5, seed), hash2(i, 6, seed)) for i in range(blobs)]
    radii = [0.05 + 0.09 * hash2(i, 7, seed) for i in range(blobs)]
    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        v = y / size
        for x in range(size):
            u = x / size
            acc = 0.0
            for i, (cx, cy) in enumerate(centers):
                # 環面距離：斑塊可以跨越 UV 邊界，否則槍身會浮出一條縫
                du = abs(u - cx)
                dv = abs(v - cy)
                d = math.hypot(min(du, 1.0 - du), min(dv, 1.0 - dv))
                acc += _clamp01(1.0 - d / radii[i])
            row.append(_clamp01(0.25 + 0.6 * _smooth01(acc)))
        out.append(row)
    return out


def pat_carbon(size: int, params: dict) -> list[list[float]]:
    """碳纖維斜紋（高級標準皮）。"""
    weave = int(params.get("weave", 6))

    def f(x: int, y: int) -> float:
        u = int(x / size * weave * 2)
        v = int(y / size * weave * 2)
        phase = 1 if (u + v) % 2 == 0 else 0
        fx = (x / size * weave * 2) % 1.0
        fy = (y / size * weave * 2) % 1.0
        d = fx if phase else fy
        return _clamp01(0.30 + 0.5 * math.sin(d * math.pi))

    return _grid(size, f)


def pat_sakura(size: int, params: dict) -> list[list[float]]:
    """花瓣散落（Higanbana / 東方風格點綴）。"""
    seed = int(params.get("seed", 37))
    count = int(params.get("count", 22))
    pts = []
    for i in range(count):
        pts.append((hash2(i, 11, seed), hash2(i, 12, seed), hash2(i, 13, seed) * math.pi,
                    0.02 + 0.03 * hash2(i, 14, seed)))
    out: list[list[float]] = []
    for y in range(size):
        row: list[float] = []
        v = y / size
        for x in range(size):
            u = x / size
            acc = 0.0
            for (cx, cy, rot, sz) in pts:
                dx = u - cx
                dy = v - cy
                # 拉長的橢圓近似花瓣
                lx = dx * math.cos(rot) + dy * math.sin(rot)
                ly = (-dx * math.sin(rot) + dy * math.cos(rot)) * 2.0
                d = math.hypot(lx, ly)
                acc += _clamp01(1.0 - d / sz)
            row.append(_clamp01(acc * 0.9 + 0.06))
        out.append(row)
    return out


PATTERNS: dict[str, object] = {
    "solid": pat_solid,
    "noise": pat_noise,
    "marble": pat_marble,
    "scales": pat_scales,
    "hex": pat_hex,
    "scanline": pat_scanline,
    "circuit": pat_circuit,
    "cracks": pat_cracks,
    "frost": pat_frost,
    "nebula": pat_nebula,
    "flame": pat_flame,
    "camo": pat_camo,
    "carbon": pat_carbon,
    "sakura": pat_sakura,
}


def pattern_names() -> list[str]:
    return sorted(PATTERNS)


def render(name: str, size: int, params: dict | None = None) -> list[list[float]]:
    """取得花紋網格；未知花紋退回 solid（避免整條管線掛掉）。"""
    fn = PATTERNS.get(name)
    if fn is None:
        return pat_solid(size, {"value": 0.5})
    return fn(size, params or {})


# --------------------------------------------------------------------- #
# 後處理：高度 → 法線
# --------------------------------------------------------------------- #
def height_to_normal(grid: list[list[float]], strength: float = 2.0) -> list[list[tuple]]:
    """Sobel 差分 → (nx, ny, nz) 單位向量（0..1 編碼在呼叫端處理）。"""
    size = len(grid)

    def at(x: int, y: int) -> float:
        return grid[y % size][x % size]

    out: list[list[tuple]] = []
    for y in range(size):
        row: list[tuple] = []
        for x in range(size):
            hl = at(x - 1, y)
            hr = at(x + 1, y)
            hd = at(x, y - 1)
            hu = at(x, y + 1)
            dx = (hr - hl) * strength
            dy = (hu - hd) * strength
            nz = 1.0
            ln = math.sqrt(dx * dx + dy * dy + nz * nz)
            row.append((-dx / ln, -dy / ln, nz / ln))
        out.append(row)
    return out


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _smooth01(v: float) -> float:
    return _clamp01(v * v * (3.0 - 2.0 * v))


def _contrast(v: float, c: float) -> float:
    return _clamp01((v - 0.5) * c + 0.5)
