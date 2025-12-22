"""
应用层入口。

运行方式：
1. python -m src.app.main          （推荐，作为模块运行）
2. python src/app/main.py          （直接运行）
3. gunicorn src.app.main:app       （生产环境）
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，以支持直接运行
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.app import create_app

app = create_app()


if __name__ == "__main__":
    # 仅用于本地开发调试，生产环境建议使用 gunicorn 等 WSGI 容器。
    app.run(host="0.0.0.0", port=5000, debug=True)
