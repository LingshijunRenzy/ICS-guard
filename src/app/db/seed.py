"""
数据库初始化种子数据。

创建预定义的角色、权限及其关联关系。
基于 docs/rbac-design.md 中定义的 RBAC 模型。
"""

from typing import Dict, List

from werkzeug.security import generate_password_hash

from . import session_scope
from .models import Permission, Role, User, role_permissions_table


# ---------------------------------------------------------------------------
# 预定义权限
# ---------------------------------------------------------------------------

PERMISSIONS: List[Dict[str, str]] = [
    # 拓扑与状态
    {"code": "topology:read", "display_name": "拓扑只读", "resource": "topology", "action": "read"},
    # 节点控制
    {"code": "node:control", "display_name": "节点控制", "resource": "node", "action": "control"},
    # 连接控制
    {"code": "link:control", "display_name": "连接控制", "resource": "link", "action": "control"},
    # 策略管理
    {"code": "policy:read", "display_name": "策略只读", "resource": "policy", "action": "read"},
    {"code": "policy:write", "display_name": "策略写入", "resource": "policy", "action": "write"},
    {"code": "policy:execute", "display_name": "策略执行", "resource": "policy", "action": "execute"},
    # 告警
    {"code": "alert:read", "display_name": "告警只读", "resource": "alert", "action": "read"},
    # 蜜罐日志
    {"code": "honeypot:read", "display_name": "蜜罐日志只读", "resource": "honeypot", "action": "read"},
    # 模型与检测
    {"code": "model:read", "display_name": "模型信息只读", "resource": "model", "action": "read"},
    {"code": "model:detect", "display_name": "AI检测", "resource": "model", "action": "detect"},
    # 用户管理
    {"code": "user:manage", "display_name": "用户管理", "resource": "user", "action": "manage"},
    # 审计日志
    {"code": "audit:read", "display_name": "审计日志只读", "resource": "audit", "action": "read"},
    # 自动化操作记录
    {"code": "event_log:read", "display_name": "自动化事件只读", "resource": "event_log", "action": "read"},
    {"code": "flow_history:read", "display_name": "检测历史只读", "resource": "flow_history", "action": "read"},
    # 偏好配置
    {"code": "preference:read", "display_name": "偏好只读", "resource": "preference", "action": "read"},
    {"code": "preference:write", "display_name": "偏好写入", "resource": "preference", "action": "write"},
]


# ---------------------------------------------------------------------------
# 预定义角色及其权限
# ---------------------------------------------------------------------------

ROLES: Dict[str, Dict] = {
    "admin": {
        "display_name": "管理员",
        "description": "拥有全部权限，包括用户管理和系统配置",
        "is_system": True,
        "permissions": [
            "topology:read",
            "node:control",
            "link:control",
            "policy:read",
            "policy:write",
            "policy:execute",
            "alert:read",
            "honeypot:read",
            "model:read",
            "model:detect",
            "user:manage",
            "audit:read",
            "event_log:read",
            "flow_history:read",
            "preference:read",
            "preference:write",
        ],
    },
    "operator": {
        "display_name": "运维人员",
        "description": "可执行节点/连接/策略的控制操作，但不能管理用户",
        "is_system": True,
        "permissions": [
            "topology:read",
            "node:control",
            "link:control",
            "policy:read",
            "policy:write",
            "policy:execute",
            "alert:read",
            "honeypot:read",
            "model:read",
            "model:detect",
            "audit:read",
            "event_log:read",
            "flow_history:read",
            "preference:read",
            "preference:write",
        ],
    },
    "analyst": {
        "display_name": "安全分析师",
        "description": "可查看告警/蜜罐日志、执行 AI 检测，但不能控制网络",
        "is_system": True,
        "permissions": [
            "topology:read",
            "policy:read",
            "alert:read",
            "honeypot:read",
            "model:read",
            "model:detect",
            "audit:read",
            "event_log:read",
            "flow_history:read",
            "preference:read",
            "preference:write",
        ],
    },
    "viewer": {
        "display_name": "只读用户",
        "description": "只能查看拓扑、状态、策略列表等，不能执行任何写操作",
        "is_system": True,
        "permissions": [
            "topology:read",
            "policy:read",
            "alert:read",
            "honeypot:read",
            "model:read",
            "event_log:read",
            "flow_history:read",
            "preference:read",
        ],
    },
}


# ---------------------------------------------------------------------------
# 种子函数
# ---------------------------------------------------------------------------


def seed_permissions() -> Dict[str, int]:
    """
    创建或更新预定义权限。

    返回权限 code -> permission_id 的映射。
    """
    permission_map: Dict[str, int] = {}

    with session_scope() as session:
        for perm_data in PERMISSIONS:
            code = perm_data["code"]
            perm = session.query(Permission).filter_by(code=code).first()

            if perm is None:
                perm = Permission(
                    code=code,
                    display_name=perm_data.get("display_name"),
                    resource=perm_data["resource"],
                    action=perm_data["action"],
                )
                session.add(perm)
                session.flush()  # 获取 ID
                print(f"  + 创建权限: {code}")
            else:
                # 更新显示名称
                perm.display_name = perm_data.get("display_name")

            permission_map[code] = perm.id

    return permission_map


def seed_roles(permission_map: Dict[str, int]) -> Dict[str, int]:
    """
    创建或更新预定义角色及其权限关联。

    Args:
        permission_map: 权限 code -> permission_id 的映射

    Returns:
        角色 name -> role_id 的映射
    """
    role_map: Dict[str, int] = {}

    with session_scope() as session:
        for role_name, role_data in ROLES.items():
            role = session.query(Role).filter_by(name=role_name).first()

            if role is None:
                role = Role(
                    name=role_name,
                    display_name=role_data.get("display_name"),
                    description=role_data.get("description"),
                    is_system=role_data.get("is_system", False),
                )
                session.add(role)
                session.flush()  # 获取 ID
                print(f"  + 创建角色: {role_name}")
            else:
                # 更新基本信息
                role.display_name = role_data.get("display_name")
                role.description = role_data.get("description")

            role_map[role_name] = role.id

            # 获取当前角色已有的权限 ID
            existing_perm_ids = set()
            result = session.execute(
                role_permissions_table.select().where(
                    role_permissions_table.c.role_id == role.id
                )
            )
            for row in result:
                existing_perm_ids.add(row.permission_id)

            # 需要添加的权限
            target_perm_codes = set(role_data.get("permissions", []))
            for perm_code in target_perm_codes:
                perm_id = permission_map.get(perm_code)
                if perm_id and perm_id not in existing_perm_ids:
                    session.execute(
                        role_permissions_table.insert().values(
                            role_id=role.id,
                            permission_id=perm_id,
                        )
                    )
                    print(f"    + 为角色 {role_name} 添加权限: {perm_code}")

    return role_map


def seed_all() -> None:
    """
    执行完整的种子数据初始化。

    包括：
    1. 创建/更新所有预定义权限
    2. 创建/更新所有预定义角色
    3. 建立角色-权限关联
    """
    print("=== 初始化 RBAC 种子数据 ===")

    print("\n[1/2] 初始化权限...")
    permission_map = seed_permissions()
    print(f"  共 {len(permission_map)} 个权限")

    print("\n[2/2] 初始化角色...")
    role_map = seed_roles(permission_map)
    print(f"  共 {len(role_map)} 个角色")

    # 额外：硬编码创建一个 admin 管理员账户（用户名/密码均为 admin）
    print("\n[extra] 创建默认管理员用户 admin/admin ...")
    with session_scope() as session:
        user = session.query(User).filter_by(username="admin").first()
        if user is None:
            user = User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                display_name="默认管理员",
                is_active=True,
            )
            # 绑定 admin 角色（如果已存在）
            admin_role_id = role_map.get("admin")
            if admin_role_id is not None:
                admin_role = session.get(Role, admin_role_id)
                if admin_role is not None:
                    user.roles.append(admin_role)

            session.add(user)
            session.flush()
            print(f"  + 创建默认管理员用户: username=admin, password=admin, id={user.id}")
        else:
            print("  - 已存在用户名为 admin 的用户，跳过创建")

    print("\n=== 种子数据初始化完成 ===")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 先确保表结构存在
    from . import init_db

    print("初始化数据库表结构...")
    init_db()

    # 执行种子数据初始化
    seed_all()
