"""
tools/skins — VANTA 槍皮（武器造型）系統
========================================
資料驱动的武器造型目錄（catalog）＋程序化紋理產生器。

模組：
  * catalog   — 造型系列 / 單品 / 升級等級 / 色板（唯一資料來源）
  * patterns  — 程序化花紋演算法（噪訊 / 龍鱗 / 电路 / 裂縫 / 星雲…）
  * png       — 零依賴 PNG 寫入器（stdlib zlib 而已）
  * emit      — 產生 assets/skins/*.{json,svg,png} 供 Godot / 展示台使用

設計原則（與本專案其他工具鏈一致）：
  1. 零第三方依賴、全部確定性（同 seed → 同位元組輸出）。
  2. 「資料 → 渲染」分離：Godot / 網頁展示台都只讀 JSON，不硬編碼造型。
  3. 每個造型同時定義「材質 + 特效 + 音效 + 升級」，让槍皮不只是換色。
"""

from tools.skins.catalog import (  # noqa: F401
    COLLECTIONS,
    SKINS,
    TIERS,
    WeaponSkin,
    SkinCollection,
    collect,
    skin_by_id,
    skins_for_weapon,
    validate_catalog,
)

__all__ = [
    "COLLECTIONS", "SKINS", "TIERS", "WeaponSkin", "SkinCollection",
    "collect", "skin_by_id", "skins_for_weapon", "validate_catalog",
]
