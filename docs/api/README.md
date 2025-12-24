# ICS-Guard API 文档

## 概述

本文档描述了ICS-Guard系统中使用的，应用层与控制层交互的API，包括用于配置和控制操作的RESTful API。
本文档默认所有API请求的发送方是应用层，接收方是控制层。

## 数据模型

### 核心概念

#### 节点 (Node)
网络中的实体设备或虚拟组件，如交换机、PLC、蜜罐等。

属性：
- `id`: string, 节点唯一标识符
- `name`: string, 节点名称
- `type`: string, 节点类型，支持以下值：
  - `'plc'`: 可编程逻辑控制器
  - `'hmi'`: 人机界面
  - `'switch'`: 交换机
  - `'router'`: 路由器
  - `'sensor'`: 传感器
  - `'actuator'`: 执行器
  - `'firewall'`: 防火墙
  - `'server'`: 服务器
  - `'honeypot'`: 蜜罐
  - `'node'`: 通用节点
  - `'connection'`: 连接
  - `'flow'`: 流量
  - `'access'`: 访问控制
- `ip`: string, 节点IP地址
- `status`: string, 节点状态 (例如: online, offline, maintenance)

#### 连接 (Link)
节点之间的逻辑或物理连接。

属性：
- `id`: string, 连接唯一标识符
- `source`: string, 源节点ID
- `target`: string, 目标节点ID
- `bandwidth`: number, 带宽 (Mbps)
- `status`: string, 连接状态 (例如: active, inactive, degraded)

#### 状态 (Status)
节点或连接的实时运行状态和性能指标。

节点状态属性：
- `node_id`: string, 节点ID
- `status`: string, 当前状态
- `last_updated`: string, 最后更新时间 (ISO 8601格式)
- `metrics`: object, 性能指标
  - `cpu_usage`: number, CPU使用率 (%)
  - `memory_usage`: number, 内存使用率 (%)
  - `network_throughput`: number, 网络吞吐量 (Mbps)

连接状态属性：
- `link_id`: string, 连接ID
- `status`: string, 当前状态
- `last_updated`: string, 最后更新时间 (ISO 8601格式)
- `metrics`: object, 性能指标
  - `bandwidth_usage`: number, 带宽使用率 (%)
  - `latency`: number, 延迟 (ms)
  - `packet_loss`: number, 丢包率 (%)

#### 流 (Flow)
网络中的数据流信息，包含五元组和其他关键特征。

属性：
- `id`: string, 流唯一标识符
- `src_ip`: string, 源IP地址
- `dst_ip`: string, 目的IP地址
- `src_port`: number, 源端口号
- `dst_port`: number, 目的端口号
- `protocol`: string, 协议类型
- `start_time`: string, 流开始时间 (ISO 8601格式)
- `end_time`: string, 流结束时间 (ISO 8601格式)
- `duration`: number, 流持续时间(秒)
- `pkt_count`: number, 包数量
- `byte_count`: number, 字节数
- `pkt_rate`: number, 包率 (pkt/s)
- `byte_rate`: number, 字节率 (bytes/s)
- `func_code_entropy`: number, 功能码熵
- `reg_addr_std`: number, 目标寄存器地址标准差
- `status`: string, 流状态 (active, inactive, completed)
- `policy_effects` (可选): 数组，记录策略命中与动作结果
  - `id`: string, 策略 ID
  - `name`: string, 策略名称
  - `action`: string, allow | block | redirect | throttle | isolate | inspect | log
  - `priority`: number, 策略优先级
  - `matched_at`: string, 触发时间 (ISO 8601)
  - `result`: string, applied | skipped | error
  - `reason`: string, 失败或跳过原因（可选）
- `redirect_to` (可选): { `dst_ip`: string, `dst_port`: number, `node_id`: string (可选) }
- `final_dst` (可选): { `dst_ip`: string, `dst_port`: number }，实际送达/尝试的终点
- `blocked` (可选): boolean，是否被阻断
- `blocked_at` (可选): string，阻断时间 (ISO 8601)
- `block_reason` (可选): string，阻断原因
- `path_hops` (可选): 数组，表示经过的节点路径（用于区分多跳/不同路径）
  - `node_id`: string
  - `ip`: string (可选)
  - `type`: string (可选)
  - `entered_at`: string (可选)，数据包首次进入该节点的时间（ISO 8601）
  - `left_at`: string (可选)，数据包离开该节点的时间（ISO 8601）

#### 策略 (Policy)
系统中的策略定义，用于控制节点、连接和流的行为。

属性：
- `id`: string, 策略唯一标识符
- `name`: string, 策略名称
- `description`: string, 策略描述
- `type`: string, 策略类型 (node, connection, flow)
- `subtype`: string, 策略子类型 (例如: access_control, bandwidth_control, anomaly_blocking)
- `status`: string, 策略状态 (active, disabled, pending)
- `priority`: number, 策略优先级，数值越小优先级越高
- `scope`: object, 策略作用范围
  - `target_type`: string, 目标类型 (device, ip_range, vlan, protocol)
  - `target_identifier`: string, 目标标识符
  - `target_ip`: string, 目标IP地址 (可选)
  - `target_mac`: string, 目标MAC地址 (可选)
  - `device_type`: string, 设备类型 (PLC, HMI, SCADA, RTU, sensor) (可选)
- `conditions`: object, 策略触发条件
  - `time_window`: object, 时间窗口 (可选)
    - `start_time`: string, 开始时间 (HH:MM格式)
    - `end_time`: string, 结束时间 (HH:MM格式)
    - `days`: array, 生效日期 (monday, tuesday, wednesday, thursday, friday, saturday, sunday)
  - `trigger_thresholds`: object, 触发阈值 (可选)
    - `packet_rate`: number, 包率阈值 (包/秒)
    - `byte_rate`: number, 字节率阈值 (字节/秒)
    - `connection_count`: number, 连接数阈值
    - `duration_seconds`: number, 持续时间阈值 (秒)
    - `function_code_entropy`: number, 功能码熵阈值
  - `protocol_specific`: object, 协议特定条件 (可选)
    - `allowed_function_codes`: array, 允许的功能码列表
    - `denied_function_codes`: array, 拒绝的功能码列表
    - `register_ranges`: array, 寄存器范围列表
      - `start_address`: number, 起始地址
      - `end_address`: number, 结束地址
      - `access_type`: string, 访问类型 (read_only, read_write)
- `actions`: object, 策略动作
  - `primary_action`: string, 主要动作 (allow, block, redirect, throttle, isolate, shutdown, disable, terminate)
  - `secondary_actions`: array, 次要动作列表
    - `action_type`: string, 动作类型 (log, redirect, alert)
    - `log_level`: string, 日志级别 (info, warning, alert, critical) (仅当action_type为log时)
    - `log_message`: string, 日志消息 (仅当action_type为log时)
    - `redirect_target`: string, 重定向目标 (仅当action_type为redirect时)
    - `redirect_condition`: string, 重定向条件 (仅当action_type为redirect时)
    - `alert_level`: string, 告警级别 (low, medium, high, critical) (仅当action_type为alert时)
    - `notification_channels`: array, 通知渠道 (email, sms, syslog) (仅当action_type为alert时)
  - `recovery_action`: string, 恢复动作 (例如: auto_disable_after_5min)
  - `rate_limit`: object, 速率限制 (可选)
    - `bandwidth_mbps`: number, 带宽限制 (Mbps)
    - `packets_per_second`: number, 包速率限制 (包/秒)
    - `burst_size`: number, 突发大小
- `monitoring`: object, 监控配置
  - `enable_statistics`: boolean, 是否启用统计
  - `sample_interval_seconds`: number, 采样间隔 (秒)
  - `alert_thresholds`: object, 告警阈值
    - `cpu_usage_percent`: number, CPU使用率阈值 (%)
    - `memory_usage_percent`: number, 内存使用率阈值 (%)
    - `disk_usage_percent`: number, 磁盘使用率阈值 (%)
    - `connection_attempts`: number, 连接尝试次数阈值
  - `health_check_interval`: number, 健康检查间隔 (秒)
- `metadata`: object, 元数据
  - `created_by`: string, 创建者
  - `created_at`: string, 创建时间 (ISO 8601格式)
  - `updated_at`: string, 更新时间 (ISO 8601格式)
  - `version`: number, 版本号
  - `tags`: array, 标签列表
  - `risk_level`: string, 风险级别 (low, medium, high, critical)
  - `compliance_requirements`: array, 合规要求 (例如: IEC62443, NIST_SP800-82)

### 响应结构
所有的响应体均为JSON格式，结构如下：

```json
{
    "code": "200",
    "message": "请求成功",
    "metadata": {
        "timestamp": "2025-04-05T12:00:00Z"
    },
    "data": {}
}
```
- `code`：请求状态码，成功时为HTTP状态码200，失败时为具体的错误码。
- `message`：人类可读的状态描述。
- `metadata`：包含请求处理时间等元数据。
- `data`：请求成功时包含的实际数据，失败时为空。

在下文的API详情中介绍的响应体结构，默认是"data"字段包含的实际数据，忽略外层的"code"、"message"、"metadata"字段。

### 错误处理

API使用标准HTTP状态码来指示请求的成功或失败。在出现错误时，响应体的code为具体的错误码，message为人类可读的错误信息。
```json
{
    "code": "400",
    "message": "无效的请求参数"
}
```
常见的HTTP状态码：
- 200 OK - 请求成功
- 400 Bad Request - 无效的请求参数
- 401 Unauthorized - 缺少或无效的认证
- 403 Forbidden - 权限不足
- 404 Not Found - 资源未找到
- 500 Internal Server Error - 服务器内部错误

## 鉴权
使用单向鉴别，鉴别者是控制层，被鉴别者是应用层。

使用基于JWT的认证机制，应用层在请求中包含访问令牌（Bearer Token），控制器在收到请求后验证令牌的有效性。

除了首次登录和刷新令牌外，所有的请求包含的令牌都是访问令牌（Access Token）。
在刷新令牌时，应用层需要包含刷新令牌（Refresh Token）。
刷新令牌的有效期长于访问令牌

完整交互流程：
1. 首次登录时，应用层向认证中心请求初始访问令牌。
2. 认证中心验证客户端凭证，若有效，返回访问令牌和刷新令牌。
3. 应用层在后续请求中包含访问令牌，控制器验证令牌有效性。
4. 若令牌过期，应用层使用刷新令牌请求新的访问令牌。
5. 若刷新令牌也过期，应用层需要重新登录获取新的访问令牌和刷新令牌。

### 1. 获取访问令牌
- **URL**: `/auth/token`
- **方法**: `POST`
- **描述**: 应用层向认证中心请求初始访问令牌
- **请求体** (application/json):
  ```json
  {
    "client_id": "string",
    "client_secret": "string"
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "access_token": "string",
      "token_type": "Bearer",
      "expires_in": "number",
      "refresh_token": "string"
    }
    ```
- **错误响应**:
  - 400 Bad Request: 缺少必需参数
  - 401 Unauthorized: 客户端凭证无效

### 2. 刷新访问令牌
- **URL**: `/auth/refresh`
- **方法**: `GET`
- **描述**: 使用刷新令牌获取新的访问令牌。刷新令牌通过Authorization头部传递。
- **请求参数**: 无
- **请求头**:
  ```
  Authorization: Bearer REFRESH_TOKEN
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "access_token": "string",
      "token_type": "Bearer",
      "expires_in": "number",
      "refresh_token": "string"
    }
    ```
- **错误响应**:
  - 400 Bad Request: 缺少必需参数
  - 401 Unauthorized: 刷新令牌无效或过期
- **示例请求**:
  ```bash
  curl -H "Authorization: Bearer REFRESH_TOKEN" http://localhost:8000/auth/refresh
  ```

### 3. 验证令牌
- **URL**: `/auth/verify`
- **方法**: `POST`
- **描述**: 控制器验证令牌有效性
- **请求体** (application/json):
  ```json
  {
    "token": "string"
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "valid": true,
      "client_id": "string",
      "expires_at": "string"
    }
    ```
- **错误响应**:
  - 400 Bad Request: 缺少必需参数
  - 401 Unauthorized: 令牌无效或过期

### 4. 撤销令牌
- **URL**: `/auth/revoke`
- **方法**: `POST`
- **描述**: 主动撤销令牌（用于安全退出或紧急情况）
- **请求体** (application/json):
  ```json
  {
    "token": "string"
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "revoked": true
    }
    ```
- **错误响应**:
  - 400 Bad Request: 缺少必需参数
  - 401 Unauthorized: 令牌无效



## RESTful API接口详解

### 1. 拓扑管理

#### 获取网络拓扑信息
- **URL**: `/topology`
- **方法**: `GET`
- **描述**: 获取当前网络拓扑信息，包括所有节点和连接关系
- **请求参数**: 无
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "nodes": [
        {
          "id": "string",
          "name": "string",
          "type": "string",
          "ip": "string",
          "status": "string"
        }
      ],
      "links": [
        {
          "source": "string",
          "target": "string",
          "bandwidth": "number",
          "status": "string"
        }
      ]
    }
    ```
- **示例请求**:
  ```bash
  curl -H "Authorization: Bearer YOUR_API_TOKEN" http://localhost:8000/topology
  ```
- **示例响应**:
  ```json
  {
    "nodes": [
      {"id": "sw1", "name": "Switch1", "type": "switch", "ip": "10.0.0.1", "status": "online"},
      {"id": "plc1", "name": "PLC1", "type": "plc", "ip": "10.0.0.10", "status": "online"},
      {"id": "hp1", "name": "Honeypot1", "type": "honeypot", "ip": "10.0.0.20", "status": "online"}
    ],
    "links": [
      {"source": "sw1", "target": "plc1", "bandwidth": 100, "status": "active"},
      {"source": "sw1", "target": "hp1", "bandwidth": 100, "status": "active"}
    ]
  }
  ```

### 2. 状态监控

#### 获取节点状态
- **URL**: `/nodes/{node_id}/status`
- **方法**: `GET`
- **描述**: 获取特定节点的实时状态信息
- **路径参数**:
  - `node_id`: string, 节点唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "node_id": "string",
      "status": "string",
      "last_updated": "string",
      "metrics": {
        "cpu_usage": "number",
        "memory_usage": "number",
        "network_throughput": "number"
      }
    }
    ```

#### 获取连接状态
- **URL**: `/links/{link_id}/status`
- **方法**: `GET`
- **描述**: 获取特定连接的实时状态信息
- **路径参数**:
  - `link_id`: string, 连接唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "link_id": "string",
      "status": "string",
      "last_updated": "string",
      "metrics": {
        "bandwidth_usage": "number",
        "latency": "number",
        "packet_loss": "number"
      }
    }
    ```

### 3. 节点操作

#### 启动节点
- **URL**: `/nodes/{node_id}/start`
- **方法**: `POST`
- **描述**: 启动指定节点
- **路径参数**:
  - `node_id`: string, 节点唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Node started successfully",
      "node_id": "string"
    }
    ```

#### 停止节点
- **URL**: `/nodes/{node_id}/stop`
- **方法**: `POST`
- **描述**: 停止指定节点
- **路径参数**:
  - `node_id`: string, 节点唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Node stopped successfully",
      "node_id": "string"
    }
    ```

#### 重启节点
- **URL**: `/nodes/{node_id}/restart`
- **方法**: `POST`
- **描述**: 重启指定节点
- **路径参数**:
  - `node_id`: string, 节点唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Node restarted successfully",
      "node_id": "string"
    }
    ```

### 4. 连接操作

#### 启用连接
- **URL**: `/links/{link_id}/enable`
- **方法**: `POST`
- **描述**: 启用指定连接
- **路径参数**:
  - `link_id`: string, 连接唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Link enabled successfully",
      "link_id": "string"
    }
    ```

#### 禁用连接
- **URL**: `/links/{link_id}/disable`
- **方法**: `POST`
- **描述**: 禁用指定连接
- **路径参数**:
  - `link_id`: string, 连接唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Link disabled successfully",
      "link_id": "string"
    }
    ```

### 5. 策略管理

#### 创建策略
- **URL**: `/policies`
- **方法**: `POST`
- **描述**: 创建新的策略
- **请求体** (application/json):
  ```json
  {
    "policy": {
      "id": "string",
      "name": "string",
      "description": "string",
      "type": "string",
      "subtype": "string",
      "status": "string",
      "priority": "number",
      "scope": {
        "target_type": "string",
        "target_identifier": "string"
      },
      "conditions": {},
      "actions": {
        "primary_action": {
          "action_type": "allow",
          "action_params": {}
        },
        "secondary_actions": [
          {
            "action_type": "log",
            "action_params": {
              "log_level": "info",
              "log_message": "示例日志"
            }
          }
        ]
      },
      "metadata": {
        "created_by": "string"
      }
    }
  }
  ```
- **成功响应**:
  - 状态码: 201 Created
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Policy created successfully",
      "policy_id": "string"
    }
    ```

#### 获取策略
- **URL**: `/policies/{policy_id}`
- **方法**: `GET`
- **描述**: 获取指定策略的详细信息
- **路径参数**:
  - `policy_id`: string, 策略唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "policy": {
        "id": "string",
        "name": "string",
      "description": "string",
      "type": "string",
      "subtype": "string",
      "status": "string",
      "priority": "number",
      "scope": {
        "target_type": "string",
        "target_identifier": "string"
      },
      "conditions": {},
      "actions": {
        "primary_action": {
          "action_type": "string",
          "action_params": {}
        },
        "secondary_actions": [
          {
            "action_type": "string",
            "action_params": {}
          }
        ]
      },
      "monitoring": {},
      "metadata": {}
      }
    }
    ```

#### 更新策略
- **URL**: `/policies/{policy_id}`
- **方法**: `PUT`
- **描述**: 更新指定策略的配置
- **路径参数**:
  - `policy_id`: string, 策略唯一标识符
- **请求体** (application/json):
  ```json
  {
    "policy": {
      "name": "string",
      "description": "string",
      "status": "string",
      "priority": "number",
      "conditions": {},
      "actions": {}
    }
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Policy updated successfully",
      "policy_id": "string"
    }
    ```

#### 删除策略
- **URL**: `/policies/{policy_id}`
- **方法**: `DELETE`
- **描述**: 删除指定的策略
- **路径参数**:
  - `policy_id`: string, 策略唯一标识符
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Policy deleted successfully",
      "policy_id": "string"
    }
    ```

#### 应用策略
- **URL**: `/policies/{policy_id}/apply`
- **方法**: `POST`
- **描述**: 应用指定的策略到目标对象
- **路径参数**:
  - `policy_id`: string, 策略唯一标识符
- **请求体** (application/json):
  ```json
  {
    "target_nodes": ["string"],
    "target_links": ["string"],
    "target_flows": ["string"]
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Policy applied successfully",
      "policy_id": "string"
    }
    ```

#### 撤销策略
- **URL**: `/policies/{policy_id}/revoke`
- **方法**: `POST`
- **描述**: 撤销已应用的策略
- **路径参数**:
  - `policy_id`: string, 策略唯一标识符
- **请求体** (application/json):
  ```json
  {
    "target_nodes": ["string"],
    "target_links": ["string"],
    "target_flows": ["string"]
  }
  ```
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "status": "success",
      "message": "Policy revoked successfully",
      "policy_id": "string"
    }
    ```

#### 列出所有策略
- **URL**: `/policies`
- **方法**: `GET`
- **描述**: 获取所有策略的列表
- **请求参数**:
  - `type` (可选): string, 策略类型 (node, connection, flow)
  - `status` (可选): string, 策略状态 (active, disabled, pending)
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "policies": [
        {
          "id": "string",
          "name": "string",
          "type": "string",
          "status": "string",
          "priority": "number",
          "metadata": {
            "created_at": "string"
          }
        }
      ]
    }
    ```

### 6. 统计与监控

#### 获取节点性能统计
- **URL**: `/nodes/stats`
- **方法**: `GET`
- **描述**: 获取所有节点的性能统计数据
- **请求参数**:
  - `start_time` (可选): string, ISO 8601格式开始时间
  - `end_time` (可选): string, ISO 8601格式结束时间
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "stats": [
        {
          "node_id": "string",
          "timestamp": "string",
          "cpu_usage": "number",
          "memory_usage": "number",
          "network_throughput": "number"
        }
      ]
    }
    ```

#### 获取连接性能统计
- **URL**: `/links/stats`
- **方法**: `GET`
- **描述**: 获取所有连接的性能统计数据
- **请求参数**:
  - `start_time` (可选): string, ISO 8601格式开始时间
  - `end_time` (可选): string, ISO 8601格式结束时间
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "stats": [
        {
          "link_id": "string",
          "timestamp": "string",
          "bandwidth_usage": "number",
          "latency": "number",
          "packet_loss": "number"
        }
      ]
    }
    ```

#### 获取安全告警
- **URL**: `/alerts`
- **方法**: `GET`
- **描述**: 获取安全告警信息
- **请求参数**:
  - `start_time` (可选): string, ISO 8601格式开始时间
  - `end_time` (可选): string, ISO 8601格式结束时间
  - `severity` (可选): string, 告警级别 (low, medium, high)
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "alerts": [
        {
          "id": "string",
          "timestamp": "string",
          "type": "string",
          "severity": "string",
          "source_ip": "string",
          "description": "string"
        }
      ]
    }
    ```

### 5. 蜜罐管理

#### 获取蜜罐日志
- **URL**: `/honeypot/logs`
- **方法**: `GET`
- **描述**: 获取蜜罐捕获的日志信息
- **请求参数**:
  - `start_time` (可选): string, ISO 8601格式开始时间
  - `end_time` (可选): string, ISO 8601格式结束时间
- **成功响应**:
  - 状态码: 200 OK
  - 内容类型: application/json
  - 响应体格式:
    ```json
    {
      "logs": [
        {
          "id": "string",
          "timestamp": "string",
          "source_ip": "string",
          "request": "string",
          "response": "string"
        }
      ]
    }
    ```

## Event API (WebSocket)接口详解

实时通知通过WebSocket连接传递：

### 1. 网络状态更新
- **连接端点**: `/ws/network-status`
- **描述**: 实时推送网络状态变化
- **消息格式**:
  ```json
  {
    "event": "network_status_update",
    "timestamp": "string",
    "data": {
      "node_id": "string",
      "status": "string"
    }
  }
  ```

### 2. 流量异常通知
- **连接端点**: `/ws/traffic-anomalies`
- **描述**: 实时推送流量异常检测结果
- **消息格式**:
  ```json
  {
    "event": "traffic_anomaly",
    "timestamp": "string",
    "data": {
      "flow_id": "string",
      "src_ip": "string",
      "dst_ip": "string",
      "anomaly_score": "number",
      "details": "string"
    }
  }
  ```

### 3. 蜜罐交互告警
- **连接端点**: `/ws/honeypot-alerts`
- **描述**: 实时推送蜜罐捕获的攻击行为
- **消息格式**:
  ```json
  {
    "event": "honeypot_interaction",
    "timestamp": "string",
    "data": {
      "source_ip": "string",
      "request": "string",
      "timestamp": "string"
    }
  }
  ```

### 4. 拓扑变更通知
- **连接端点**: `/ws/topology-changes`
- **描述**: 实时推送网络拓扑变化
- **消息格式**:
  ```json
  {
    "event": "topology_change",
    "timestamp": "string",
    "data": {
      "change_type": "string",
      "details": {}
    }
  }
  ```

### 5. 流状态更新
- **连接端点**: `/ws/flow-updates`
- **描述**: 实时推送流状态变化和特征数据
- **消息格式**:
  ```json
  {
    "event": "flow_update",
    "timestamp": "string",
    "data": {
      "flow": {
        "id": "string",
        "src_ip": "string", 
        "dst_ip": "string",
        "src_port": "number",
        "dst_port": "number", 
        "protocol": "string",
        "start_time": "string",
        "end_time": "string",
        "duration": "number",
        "pkt_count": "number",
        "byte_count": "number",
        "pkt_rate": "number",
        "byte_rate": "number",
        "func_code_entropy": "number",
        "reg_addr_std": "number",
        "status": "string",
        "policy_effects": [
          {
            "id": "string",
            "name": "string",
            "action": "block",
            "priority": 10,
            "matched_at": "2025-12-23T08:51:46.267Z",
            "result": "applied",
            "reason": "matched rule#10"
          }
        ],
        "blocked": true,
        "blocked_at": "2025-12-23T08:51:46.300Z",
        "block_reason": "policy block",
        "redirect_to": {
          "dst_ip": "10.0.0.99",
          "dst_port": 502
        },
        "final_dst": {
          "dst_ip": "10.0.0.99",
          "dst_port": 502
        },
        "path_hops": [
          {"node_id": "sw1", "ip": "10.0.0.1"},
          {"node_id": "fw1", "ip": "10.0.0.254"},
          {"node_id": "plc1", "ip": "10.0.0.10"}
        ]
      }
    }
  }
  ```

### 6. 节点指标更新
- **连接端点**: `/ws/node-metrics`
- **描述**: 实时推送节点的性能指标数据（高频），用于详情面板或实时图表展示。
- **消息格式**:
  ```json
  {
    "event": "node_metrics_update",
    "timestamp": "string",
    "data": {
      "node_id": "string",
      "metrics": {
        "cpu_usage": "number",
        "memory_usage": "number",
        "network_throughput": "number"
      }
    }
  }
  ```