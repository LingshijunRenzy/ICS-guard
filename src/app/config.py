import os
from flask import Flask


def load_config(app: Flask) -> None:
    """
    加载基础配置。

    当前只放最小必需项，后续根据需要扩展。
    """
    app.config.update(
        ENV=os.getenv("ICS_GUARD_ENV", "development"),
        DEBUG=os.getenv("ICS_GUARD_DEBUG", "false").lower() == "true",
        CONTROLLER_BASE_URL=os.getenv("ICS_GUARD_CONTROLLER_URL", "http://localhost:8000"),
        MODEL_DIR=os.getenv("ICS_GUARD_MODEL_DIR", "models"),
    )



