"""
ICS-Guard 应用层数据库模型定义。

包含用户、角色、权限、审计日志、偏好配置等表结构。
基于 docs/rbac-design.md 中定义的 RBAC 模型。
"""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


# ---------------------------------------------------------------------------
# 枚举定义
# ---------------------------------------------------------------------------


class RoleEnum(str):
    """预定义角色枚举（仅作参考，实际角色存储在 app_roles 表）。"""

    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class PreferenceScopeEnum(str):
    """偏好配置作用域枚举。"""

    GLOBAL = "global"
    USER = "user"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 关联表（使用 Table 而非 ORM 模型，避免外键歧义）
# ---------------------------------------------------------------------------

# 用户-角色关联表
user_roles_table = Table(
    "app_user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("app_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), default=utc_now, nullable=False),
)

# 角色-权限关联表
role_permissions_table = Table(
    "app_role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("app_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("app_permissions.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_at", DateTime(timezone=True), default=utc_now, nullable=False),
)


# ---------------------------------------------------------------------------
# 用户表
# ---------------------------------------------------------------------------


class User(Base):
    """
    应用层 Web UI 用户表。

    仅用于 Web UI 登录，与控制层的 client_id/secret 解耦。
    """

    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关系
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles_table,
        back_populates="users",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")
    preferences: Mapped[List["Preference"]] = relationship("Preference", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"

    def has_permission(self, permission_code: str) -> bool:
        """检查用户是否拥有指定权限。"""
        for role in self.roles:
            for perm in role.permissions:
                if perm.code == permission_code:
                    return True
        return False

    def get_all_permissions(self) -> set:
        """获取用户所有权限的 code 集合。"""
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.code)
        return perms


# ---------------------------------------------------------------------------
# 角色表
# ---------------------------------------------------------------------------


class Role(Base):
    """
    角色表。

    预定义角色：admin, operator, analyst, viewer
    可扩展自定义角色。
    """

    __tablename__ = "app_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # 关系
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_roles_table,
        back_populates="roles",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions_table,
        back_populates="roles",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"


# ---------------------------------------------------------------------------
# 权限表
# ---------------------------------------------------------------------------


class Permission(Base):
    """
    权限表。

    权限标识格式：resource:action，例如 topology:read, policy:write
    """

    __tablename__ = "app_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # 关系
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_permissions_table,
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code='{self.code}')>"


# ---------------------------------------------------------------------------
# 审计日志表
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """
    审计日志表。

    记录用户在 Web UI 上的关键操作。
    """

    __tablename__ = "app_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    # 关系
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    # 索引
    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"


# ---------------------------------------------------------------------------
# 偏好配置表
# ---------------------------------------------------------------------------


class Preference(Base):
    """
    偏好配置表。

    支持全局配置（scope='global'）和用户级配置（scope='user'）。
    值以 JSON 字符串存储。
    """

    __tablename__ = "app_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global", index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # 关系
    user: Mapped[Optional["User"]] = relationship("User", back_populates="preferences")

    # 约束：同一作用域 + 用户下 key 唯一
    __table_args__ = (
        UniqueConstraint("scope", "user_id", "key", name="uq_preferences_scope_user_key"),
        Index("ix_preferences_scope_key", "scope", "key"),
    )

    def __repr__(self) -> str:
        return f"<Preference(id={self.id}, scope='{self.scope}', key='{self.key}')>"


# ---------------------------------------------------------------------------
# 会话表（可选，如果使用 DB 存储会话）
# ---------------------------------------------------------------------------


class Session(Base):
    """
    用户会话表（可选）。

    如果使用 JWT 无状态会话，可以不用此表。
    如果需要服务端会话管理或 token 黑名单，可启用此表。
    """

    __tablename__ = "app_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"


# ---------------------------------------------------------------------------
# Flow 检测结果表
# ---------------------------------------------------------------------------


class AppFlow(Base):
    """
    流检测结果表。

    存储从控制层接收到的工业流量（Flow）及其模型检测结果与状态。
    """

    __tablename__ = "app_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Flow 标识
    flow_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Flow 核心信息快照
    src_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    dst_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    src_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protocol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pkt_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    byte_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pkt_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    byte_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    func_code_entropy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reg_addr_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 新增字段（根据新版API文档）
    policy_effects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 存储JSON字符串
    redirect_to: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 存储JSON字符串
    final_dst: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 存储JSON字符串
    blocked: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    blocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    block_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    path_hops: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 存储JSON字符串

    # 检测状态字段
    detect_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    decision_level: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    prob: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 其它辅助字段
    raw_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_app_flows_src_ip_created_at", "src_ip", "created_at"),
        Index("ix_app_flows_decision_level_created_at", "decision_level", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AppFlow(id={self.id}, flow_id='{self.flow_id}', status='{self.detect_status}')>"
