"""VANTA 可程式化素材產生工具鏈 (Programmable Asset Pipeline)。

統一入口：python -m tools.cli <subcommand>

子系統：
  sfx      DSP 音效合成（槍聲/爆炸/腳步/爆頭/UI/技能/Spike）
  weapons  槍械模組化 + seed 武器產生器
  maps     程序化地圖編輯器（生成/驗證/匯出）
  vfx      粒子特效 + SVG 貼圖產生器
  fx       擊殺特效 / 事件→特效綁定表

設計原則：
  * 全部純 Python 標準庫，零第三方依賴
  * seed 驅動 → 相同 seed 產生完全相同的素材（確定性、可重現）
  * 產生器輸出標準 JSON/WAV/SVG，並與 server.game 相容（可直接進遊戲）
"""
