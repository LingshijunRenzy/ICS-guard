## ICS-Guard 应用层开发计划（TODO）

> 角色边界：应用层 = Web 后端（Flask） + 前端 Web UI + 本地 AI 推理服务  
> 职责：  
> - 向 SDN 控制层调用 REST / WebSocket API（见 `docs/api/README.md`）  
> - 对接本地检测模型（见 `docs/model-training-guide.md`、`docs/flow-feature-mapping.md`）  
> - 向前端提供统一的业务 API 与实时事件流  

---

### 一、基础工程与运行骨架

- [x] **后端工程初始化（Flask 或 FastAPI 单一选择）**
  - [x] 创建后端工程目录结构（例如 `app/` 下区分 `api`, `services`, `models`, `config`）
  - [x] 定义应用入口（例如 `app/main.py` 或 `app/__init__.py` 的 `create_app()`）
  - [x] 集中配置文件（控制层基地址、认证中心地址、JWT 公钥/密钥占位、模型文件路径等）
  - [x] 提供基础健康检查接口 `/healthz`（仅返回静态 JSON，供部署/测试使用）

- [ ] **前端工程初始化（Vue）**
  - [ ] 创建前端工程目录（例如 `web-ui/`），初始化 Vue 项目骨架
  - [ ] 预置基础路由结构：拓扑视图、流量监控、策略管理、告警中心、蜜罐日志、系统设置
  - [ ] 配置统一的 API 客户端模块（封装调用应用层后端的 HTTP / WebSocket）

- [ ] **应用层本地持久化基础（DB & ORM）**
  - [ ] 选型：首期使用 SQLite 作为默认实现，通过环境变量可切换到 PostgreSQL
  - [ ] 新增 `db` 模块，封装 `get_engine()` / `get_session()` / `session_scope()` 等基础设施
  - [ ] 在 `create_app()` 中初始化数据库连接，但保持懒加载，避免阻塞无 DB 场景（如纯单元测试）
  - [ ] 引入迁移工具（Alembic），配置基础迁移环境并创建初始迁移（用户表、审计表、偏好表）

---

### 二、与控制层的 REST API 适配层

- [x] **封装控制层 REST 客户端（面向应用层后端内部使用）**
  - [x] 在后端新建 `services/controller_client.py`（或等价模块）
  - [x] 封装与鉴权相关的调用：
    - [x] `get_token(client_id, client_secret)` → 调用 `/auth/token`
    - [x] `refresh_token(refresh_token)` → 调用 `/auth/refresh`
  - [x] 封装拓扑和状态相关接口：
    - [x] `get_topology()` → 调用 `/topology`
    - [x] `get_node_status(node_id)` → 调用 `/nodes/{node_id}/status`
    - [x] `get_link_status(link_id)` → 调用 `/links/{link_id}/status`
  - [x] 封装节点、连接控制接口：
    - [x] `start_node/stop_node/restart_node`
    - [x] `enable_link/disable_link`
  - [x] 封装策略管理接口：
    - [x] `create_policy`, `get_policy`, `update_policy`, `delete_policy`
    - [x] `apply_policy`, `revoke_policy`, `list_policies`
  - [x] 封装统计与告警接口：
    - [x] `get_node_stats`, `get_link_stats`, `get_alerts`
  - [x] 封装蜜罐日志接口：
    - [x] `get_honeypot_logs`

- [x] **实现访问令牌生命周期管理**
  - [x] 定义应用层后端内部的 Token 缓存结构（内存变量或简单缓存类）
  - [x] 在每次发起控制层请求前自动附加 `Authorization: Bearer ACCESS_TOKEN`
  - [x] 检测 401 / token 过期错误时自动尝试刷新 token，一次失败后抛出上层处理

---

### 三、与控制层的 WebSocket 事件订阅

- [x] **设计事件订阅模块接口**
  - [x] 在后端新建 `services/event_subscriber.py`（或等价模块）
  - [x] 为下列端点各定义一个订阅函数或统一配置：
    - [x] `/ws/network-status`
    - [x] `/ws/traffic-anomalies`
    - [x] `/ws/honeypot-alerts`
    - [x] `/ws/topology-changes`
    - [x] `/ws/flow-updates`

- [x] **实现 WebSocket 连接与重连逻辑**
  - [x] 使用异步事件循环维护到控制层的长连接（每个端点一个连接或复用）
  - [x] 处理异常断开和指数退避重连
  - [x] 为每类事件定义内部标准化数据结构，供应用层其它模块消费

- [ ] **向前端转发实时事件**
  - [ ] 在应用层后端暴露 WebSocket / SSE 端点，转发控制层事件给前端：
    - [ ] 前端订阅的统一事件流（如 `/ws/ui-events`），内部按 `type` 区分事件类别
  - [ ] 为告警、蜜罐事件、流量异常事件添加最小必要的字段映射（不做额外业务加工）

---

### 四、AI 模型加载与在线推理服务

- [x] **模型文件与特征配置管理**
  - [x] 根据 `docs/model-training-guide.md` 确定当前线上版本使用的模型类型（LightGBM 为主）
  - [x] 约定模型文件路径（如 `models/lightgbm_model.pkl`）和特征列配置文件（如 `models/features.json`）
  - [x] 在配置中记录：特征列名列表、标签映射规则、阈值配置（alert/throttle/block）

- [x] **实现特征向量构建逻辑**
  - [x] 针对 API `Flow` 结构，按照 `docs/flow-feature-mapping.md` 定义的映射构造输入向量：
    - [x] 使用 `src_ip`, `dst_ip`, `protocol`, `duration`, `pkt_count`, `byte_count`, `pkt_rate`, `byte_rate` 等字段
    - [x] 对 `src_port`, `dst_port`, `func_code_entropy`, `reg_addr_std` 先按约定填充缺省值，不进入特征
  - [x] 保证在线特征顺序与离线训练时保存的特征列表完全一致

- [x] **实现推理服务模块**
  - [x] 新建 `services/inference.py`（或等价模块）
  - [x] 加载 LightGBM 模型实例和特征配置（应用启动时完成）
  - [x] 暴露统一调用接口，例如 `predict_flow(flow: Flow) -> {prob, label, anomaly_score, decision_level}`
  - [x] 在内部应用阈值，将概率映射到决策等级（如 normal / alert / block / redirect）

- [ ] **对接控制层策略/动作**
  - [ ] 定义从决策等级到策略模板的映射关系（例如：block → 调用控制层流级阻断策略接口）
  - [ ] 对接最小闭环：
    - [ ] 接收某个 `Flow`（来自控制层或数据采集端）
    - [ ] 调用本地推理服务得到结果
    - [ ] 根据决策通过 `controller_client` 调用控制层 API（如创建并应用流级策略，或重定向到蜜罐）

---

### 五、应用层对外业务 API（供前端使用）

- [x] **拓扑与状态接口**
  - [x] `GET /api/topology`：包装控制层 `/topology` 响应为前端友好的格式
  - [x] `GET /api/nodes/{id}/status`：代理控制层节点状态接口
  - [x] `GET /api/links/{id}/status`：代理控制层连接状态接口

- [x] **策略管理接口（面向 UI）**
  - [x] `GET /api/policies`：列出策略简要信息（封装控制层 `/policies`）
  - [x] `GET /api/policies/{id}`：获取策略详情
  - [x] `POST /api/policies`：创建策略（限制字段为 UI 所需子集，避免暴露过多复杂字段）
  - [x] `PUT /api/policies/{id}`：更新策略
  - [x] `DELETE /api/policies/{id}`：删除策略
  - [x] `POST /api/policies/{id}/apply` / `POST /api/policies/{id}/revoke`：应用/撤销策略

- [x] **告警与蜜罐日志接口**
  - [x] `GET /api/alerts`：分页获取安全告警列表（封装控制层 `/alerts` + 必要筛选）
  - [x] `GET /api/honeypot/logs`：获取蜜罐日志（封装 `/honeypot/logs`），支持时间范围过滤

- [x] **模型与检测接口**
  - [x] `POST /api/detect/flow`：接受 `Flow` 或最小必要特征，调用本地推理服务返回检测结果
  - [x] `GET /api/model/meta`：返回当前模型版本、特征列表、阈值信息（只读，用于 UI 展示）

---

### 六、前端页面与交互逻辑

- [ ] **拓扑视图**
  - [ ] 通过 `GET /api/topology` 渲染节点/连接图
  - [ ] 点击节点/连接时，调用状态接口展示实时指标

- [ ] **实时监控与告警面板**
  - [ ] 订阅应用层 WebSocket `/ws/ui-events`，展示网络状态更新、流量异常、蜜罐告警
  - [ ] 提供告警列表视图，支持按时间/严重级别过滤

- [ ] **策略管理界面**
  - [ ] 策略列表页：展示策略名称、类型、状态、优先级
  - [ ] 策略详情/编辑页：基于 `docs/security-policies.md` 的结构渲染表单字段
  - [ ] 支持创建/更新/删除/应用/撤销策略的交互，调用对应的应用层 API

- [ ] **蜜罐日志与调查界面**
  - [ ] 列表展示蜜罐捕获的交互（来源 IP、请求、响应、时间）
  - [ ] 支持按时间范围 / 源 IP 过滤

- [ ] **模型与系统信息页面（只读）**
  - [ ] 展示当前模型版本、主要特征、阈值配置
  - [ ] 展示控制层连接状态、令牌状态概览

---

### 七、安全与配置管理（应用层视角）

- [ ] **应用层自身鉴权与多租户边界（最小实现）**
  - [ ] 为 Web UI 用户增加简单登录与会话管理（与控制层 JWT 解耦）
  - [ ] 确保对控制层 API 的调用仅由后端发起，前端不直接暴露控制层地址或令牌
  - [ ] 登录态、用户信息、会话信息持久化在应用层数据库中（见「九、应用层本地持久化与用户管理」）

- [x] **敏感配置与密钥管理**
  - [x] 所有控制层地址、认证凭据、模型路径、阈值等通过环境变量或配置文件注入
  - [x] 避免在代码中硬编码任何凭证或真实 IP

---

### 八、最小可演示闭环（MVP 验收路径）

- [ ] **MVP-1：只读监控**
  - [ ] 前端能通过应用层看到当前拓扑和节点/连接状态
  - [ ] 能查看历史告警和蜜罐日志

- [ ] **MVP-2：AI 检测 + 手动策略**
  - [ ] 能在前端手动提交一个 `Flow` 样本给 `/api/detect/flow`，看到检测结果
  - [ ] 能在前端创建并应用一个简单的流级阻断策略

- [ ] **MVP-3：自动化策略闭环**
  - [ ] 控制层推送的流更新事件经应用层触发本地检测
  - [ ] 检测判定为高风险时，应用层自动调用控制层接口下发阻断/重定向策略
  - [ ] 前端在告警中心和蜜罐日志中可看到对应的自动化响应结果


---

### 九、应用层本地持久化与用户管理

- [ ] **数据库选型与基础设施**
  - [ ] 使用 SQLite 作为默认实现，连接串例如：`sqlite:///ics_guard_app.db`
  - [ ] 通过环境变量支持切换到 PostgreSQL（如 `postgresql+psycopg://...`）
  - [ ] 封装数据库访问层（例如 `src/app/db.py`），提供 `get_engine()` / `session_scope()` 等基础工具

- [ ] **用户与权限模型（应用层 Web UI 自身）**
  - [ ] 定义用户表 `app_users`（仅用于 Web UI，不与控制层用户混用）：
    - [ ] 字段示例：`id`, `username`, `password_hash`, `role`, `is_active`, `created_at`, `updated_at`
  - [ ] 定义最小角色模型：`admin`, `operator`, `viewer`
  - [ ] 定义登录 / 登出 / 刷新会话的后端接口（如 `/api/auth/login` 等），只作用于 Web UI

- [ ] **审计日志（应用层行为）**
  - [ ] 定义审计表 `app_audit_logs`：
    - [ ] 字段示例：`id`, `user_id`, `action`, `resource`, `payload_snapshot`, `ip`, `created_at`
  - [ ] 在关键后端 API 调用处记录审计事件（例如：策略创建/更新/应用、手动触发检测等）
  - [ ] 提供只读审计查询接口（如 `/api/audit/logs`，可分页、按时间/用户过滤）

- [ ] **UI / 应用偏好配置**
  - [ ] 定义偏好表 `app_preferences`：
    - [ ] 支持全局配置（`scope = global`）与用户级配置（`scope = user`, `user_id`）
    - [ ] 使用 `key`, `value`（JSON）、`updated_at` 字段存储配置
  - [ ] 用于存储：
    - [ ] 告警列表默认过滤条件
    - [ ] 默认时间范围、图表刷新间隔等 UI 相关参数
  - [ ] 提供简单的读写接口（如 `/api/preferences`）

- [ ] **安全边界与最小实现**
  - [ ] 应用层 Web UI 登录与控制层 JWT 解耦：应用层不直接向前端暴露控制层凭证
  - [ ] 数据库中不存任何控制层 access_token / refresh_token，仅存应用层自己的会话信息

