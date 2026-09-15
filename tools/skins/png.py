"""
tools/skins/png.py — 零依賴 PNG 寫入器
======================================
只用 stdlib（struct + zlib）寫出 8-bit RGBA / RGB PNG。
供工具鏈輸出程序化槍皮紋理（albedo / emissive / normal / ORM）。

刻意不支援花俏特性（無调色板、無 interlace、单 IDAT chunk 組），
因為客戶端只需要「能被任何圖片解码器讀到的正方形貼圖」。
"""

from __future__ import annotations

import struct
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(
        ">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def encode_png(width: int, height: int, pixels: bytes, channels: int = 4,
               level: int = 9) -> bytes:
    """pixels 為 row-major、channels（3=RGB / 4=RGBA）位元組緩衝。"""
    if channels not in (3, 4):
        raise ValueError("channels must be 3 or 4")
    expected = width * height * channels
    if len(pixels) != expected:
        raise ValueError(f"pixel buffer too small: {len(pixels)} != {expected}")
    color_type = 6 if channels == 4 else 2
    stride = width * channels
    raw = bytearray()
    for y in range(height):
        raw.append(0)                                    # filter: None
        raw += pixels[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (PNG_MAGIC
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), level))
            + _chunk(b"IEND", b""))


def write_png(path: str, width: int, height: int, pixels: bytes,
              channels: int = 4) -> None:
    import os

    data = encode_png(width, height, pixels, channels)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def read_png_size(path: str) -> tuple[int, int, int]:
    """回傳 (width, height, color_type)；提供工具鏈/測試驗證輸出。"""
    with open(path, "rb") as f:
        blob = f.read(33)
    if blob[:8] != PNG_MAGIC:
        raise ValueError(f"not a PNG: {path}")
    w, h, depth, color = struct.unpack(">IIBB", blob[16:26])
    return w, h, color
