# ICS-Guard 应用层 RBAC 设计

> 本文档定义应用层 Web UI 的角色、权限与操作清单，供后端鉴权实现和前端菜单/按钮控制参考。

---

## 一、设计原则

1. **最小权限原则**：用户只能访问其职责所需的最小资源集。
2. **职责分离**：管理员、运维、分析、只读四类角色边界清晰。
3. **与控制层解耦**：应用层 RBAC 仅管理 Web UI 用户，不涉及控制层的 client_id/secret。
4. **可扩展**：权限粒度足够细，便于后续按需组合或新增角色。

---

## 二、操作清单（按资源域）

### 2.1 拓扑与状态（只读，低敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 获取拓扑 | `GET /api/topology` | `topology:read` |
| 节点状态 | `GET /api/nodes/{id}/status` | `topology:read` |
| 连接状态 | `GET /api/links/{id}/status` | `topology:read` |
| 节点统计 | `GET /api/nodes/stats` | `topology:read` |
| 连接统计 | `GET /api/links/stats` | `topology:read` |

### 2.2 节点控制（高敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 启动节点 | `POST /api/nodes/{id}/start` | `node:control` |
| 停止节点 | `POST /api/nodes/{id}/stop` | `node:control` |
| 重启节点 | `POST /api/nodes/{id}/restart` | `node:control` |

### 2.3 连接控制（高敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 启用连接 | `POST /api/links/{id}/enable` | `link:control` |
| 禁用连接 | `POST /api/links/{id}/disable` | `link:control` |

### 2.4 策略管理（中高敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 列出策略 | `GET /api/policies` | `policy:read` |
| 策略详情 | `GET /api/policies/{id}` | `policy:read` |
| 创建策略 | `POST /api/policies` | `policy:write` |
| 更新策略 | `PUT /api/policies/{id}` | `policy:write` |
| 删除策略 | `DELETE /api/policies/{id}` | `policy:write` |
| 应用策略 | `POST /api/policies/{id}/apply` | `policy:execute` |
| 撤销策略 | `POST /api/policies/{id}/revoke` | `policy:execute` |

### 2.5 告警（只读，中敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 获取告警 | `GET /api/alerts` | `alert:read` |

### 2.6 蜜罐日志（只读，中敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 获取日志 | `GET /api/honeypot/logs` | `honeypot:read` |

### 2.7 AI 模型与检测（中敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 模型元信息 | `GET /api/model/meta` | `model:read` |
| 单流检测 | `POST /api/detect/flow` | `model:detect` |
| 批量检测 | `POST /api/detect/batch` | `model:detect` |

### 2.8 用户管理（高敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 列出用户 | `GET /api/users` | `user:manage` |
| 创建用户 | `POST /api/users` | `user:manage` |
| 更新用户 | `PUT /api/users/{id}` | `user:manage` |
| 删除用户 | `DELETE /api/users/{id}` | `user:manage` |
| 登录 | `POST /api/auth/login` | 公开（无需鉴权） |
| 登出 | `POST /api/auth/logout` | 已登录用户 |

### 2.9 审计日志（只读，中敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 查看审计 | `GET /api/audit/logs` | `audit:read` |

### 2.10 偏好配置（低敏感）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 读取偏好 | `GET /api/preferences` | `preference:read` |
| 写入偏好 | `PUT /api/preferences` | `preference:write` |

### 2.11 系统（公开）

| 操作 | 接口 | 权限标识 |
|------|------|----------|
| 健康检查 | `GET /healthz` | 公开（无需鉴权） |

---

## 三、权限标识汇总

```
topology:read       # 拓扑/状态/统计只读
node:control        # 节点 start/stop/restart
link:control        # 连接 enable/disable
policy:read         # 策略只读
policy:write        # 策略 create/update/delete
policy:execute      # 策略 apply/revoke
alert:read          # 告警只读
honeypot:read       # 蜜罐日志只读
model:read          # 模型元信息只读
model:detect        # AI 检测（flow/batch）
user:manage         # 用户 CRUD
audit:read          # 审计日志只读
preference:read     # 偏好只读
preference:write    # 偏好写入
```

---

## 四、角色定义

| 角色 | 中文名 | 定位 | 典型用户 |
|------|--------|------|----------|
| `admin` | 管理员 | 拥有全部权限，包括用户管理和系统配置 | 系统管理员 |
| `operator` | 运维人员 | 可执行节点/连接/策略的控制操作，但不能管理用户 | 现场运维工程师 |
| `analyst` | 安全分析师 | 可查看告警/蜜罐日志、执行 AI 检测，但不能控制网络 | 安全团队成员 |
| `viewer` | 只读用户 | 只能查看拓扑、状态、策略列表等，不能执行任何写操作 | 审计人员、外部观察者 |

---

## 五、角色-权限矩阵

| 权限标识 | admin | operator | analyst | viewer |
|----------|:-----:|:--------:|:-------:|:------:|
| `topology:read` | ✅ | ✅ | ✅ | ✅ |
| `node:control` | ✅ | ✅ | ❌ | ❌ |
| `link:control` | ✅ | ✅ | ❌ | ❌ |
| `policy:read` | ✅ | ✅ | ✅ | ✅ |
| `policy:write` | ✅ | ✅ | ❌ | ❌ |
| `policy:execute` | ✅ | ✅ | ❌ | ❌ |
| `alert:read` | ✅ | ✅ | ✅ | ✅ |
| `honeypot:read` | ✅ | ✅ | ✅ | ✅ |
| `model:read` | ✅ | ✅ | ✅ | ✅ |
| `model:detect` | ✅ | ✅ | ✅ | ❌ |
| `user:manage` | ✅ | ❌ | ❌ | ❌ |
| `audit:read` | ✅ | ✅ | ✅ | ❌ |
| `preference:read` | ✅ | ✅ | ✅ | ✅ |
| `preference:write` | ✅ | ✅ | ✅ | ❌ |

---

## 六、实现要点

### 6.1 后端鉴权

1. **中间件/装饰器**：在需要鉴权的路由上使用装饰器检查当前用户是否拥有所需权限。
2. **权限检查逻辑**：
   - 从 JWT / Session 中获取 `user_id`
   - 查询用户角色
   - 查询角色关联的权限集合
   - 判断是否包含目标权限

### 6.2 前端控制

1. **菜单可见性**：根据用户权限隐藏无权访问的菜单项。
2. **按钮可用性**：根据权限禁用或隐藏操作按钮（如"创建策略"、"启动节点"）。
3. **API 调用兜底**：即使前端放行，后端仍需做权限校验。

### 6.3 审计关联

- 所有敏感操作（`*:control`、`*:write`、`*:execute`、`user:manage`）应记录审计日志。
- 审计日志记录：`user_id`、`action`、`resource`、`payload_snapshot`、`ip`、`timestamp`。

---

## 七、扩展建议

- **细粒度资源权限**：如需控制"只能操作某个节点/某类策略"，可扩展为 `node:control:plc1` 这种形式。
- **临时权限**：可增加 `expires_at` 字段，支持临时授权。
- **多租户**：可在用户/角色上增加 `tenant_id`，实现多租户隔离。

---

*文档版本：v1.0*  
*最后更新：2025-01-XX*

