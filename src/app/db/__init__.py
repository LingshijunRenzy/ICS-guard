"""
ICS-Guard 应用层数据库模块。

提供 SQLAlchemy 引擎、会话管理和模型基类。
默认使用 SQLite，可通过环境变量切换到 PostgreSQL。
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 数据库 URL，默认使用 SQLite
# 可通过环境变量 ICS_GUARD_DATABASE_URL 覆盖
# 示例：postgresql+psycopg://user:pass@localhost/ics_guard
DEFAULT_DATABASE_URL = "sqlite:///ics_guard_app.db"
DATABASE_URL = os.environ.get("ICS_GUARD_DATABASE_URL", DEFAULT_DATABASE_URL)

# ---------------------------------------------------------------------------
# 引擎与会话
# ---------------------------------------------------------------------------

# 创建引擎
# - SQLite 需要 check_same_thread=False 以支持多线程
# - PostgreSQL 等其他数据库不需要此参数
_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, **_engine_kwargs)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明式基类
Base = declarative_base()


def get_engine():
    """获取数据库引擎实例。"""
    return engine


def get_session() -> Session:
    """
    获取一个新的数据库会话。

    使用方需要自行管理会话的提交和关闭。
    推荐使用 session_scope() 上下文管理器。
    """
    return SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    提供一个事务性的数据库会话上下文。

    使用方式：
        with session_scope() as session:
            session.add(some_object)
            # 自动提交或回滚

    异常时自动回滚，正常退出时自动提交。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    初始化数据库表结构。

    根据 Base.metadata 中注册的模型创建所有表。
    如果表已存在，不会重复创建。
    """
    # 导入模型以确保它们被注册到 Base.metadata
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """
    删除所有表（仅用于测试/开发）。

    警告：此操作会删除所有数据！
    """
    from . import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)

