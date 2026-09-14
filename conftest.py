# 讓 pytest 將專案根目錄加入 sys.path，使 `import server.core...` 可直接使用。

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

