# 讓本機 pytest 能 import：
#   * workers/src 下的模組（match_host / ws_transport / ai_bots）
#   * 倉庫根目錄的 server 套件（部署時會被複製成 src/server，內容相同）
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # workers/
SRC = os.path.join(ROOT, "src")
REPO = os.path.dirname(ROOT)                                          # VANTA/

for p in (SRC, REPO):
    if p not in sys.path:
        sys.path.insert(0, p)
