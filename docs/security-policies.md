# 策略指南

本文档详细介绍了ICS-Guard系统中可用的各种策略类型及其使用方法。

## 策略分类

策略按照操作对象分为三类：节点级策略、连接级策略和流级策略。

## 策略结构详解

每个策略都遵循统一的结构定义，包含以下几个关键部分：

### 标识信息
- `id`: 策略唯一标识符 (字符串, 示例: "node-access-001")
- `name`: 策略名称 (字符串, 示例: "PLC-Access-Control")
- `description`: 策略详细描述 (字符串, 示例: "限制对PLC-01的访问")
- `type`: 策略类型 (枚举: node/connection/flow, 示例: "node")
- `subtype`: 策略子类型 (字符串, 示例: "access_control")
- `status`: 策略状态 (枚举: active/inactive, 示例: "active")
- `priority`: 策略优先级 (整数, 数值越小优先级越高, 示例: 100)
- `conditions`: 条件定义 (对象)
- `actions`: 动作定义 (对象)
  - `primary_action`: 主要动作（对象）
  - `secondary_actions`: 次要动作 (数组, 示例: [ { "action_type": "log", "log_level": "info", "log_message": "访问PLC-01" } ])

### 条件定义 (Conditions)
条件部分定义了策略触发所需满足的场景。条件必须与策略的作用域对象（节点、连接、流）在逻辑上保持一致。多个条件之间是 **AND** 关系，即必须同时满足所有条件才会触发动作。

#### 数值型判定操作符
所有数值型字段（如 CPU 使用率、速率、延迟等）均支持以下操作符后缀：
- `_gt`: 大于 (Greater Than)
- `_gte`: 大于等于 (Greater Than or Equal)
- `_lt`: 小于 (Less Than)
- `_lte`: 小于等于 (Less Than or Equal)
- `_eq`: 等于 (Equal)

**示例**：`"cpu_usage_gte": 80` 表示 CPU 使用率大于等于 80%。

#### 1. 节点级策略条件 (Node-level Conditions)
**场景**：当该节点本身或与其直接相关的交互满足以下条件时触发。

- **流量方向 (Traffic)**:
  - `ingress_filter`: 流入该节点的流量特征。包含 `src_ip` (源IP), `protocol` (协议), `pkt_rate` (包速率，支持操作符后缀) 等。
    - *示例*: `{"protocol": "modbus", "pkt_rate_gt": 100}`
  - `egress_filter`: 从该节点流出的流量特征。包含 `dst_ip` (目的IP), `pkt_rate` (包速率，支持操作符后缀) 等。
- **资源状态 (Resource)**:
  - `cpu_usage`: CPU 使用率百分比 (0-100，支持操作符后缀)。
  - `mem_usage`: 内存使用率百分比 (0-100，支持操作符后缀)。
- **安全状态 (Security)**:
  - `anomaly_detected`: 节点是否被系统判定为存在异常行为 (布尔值)。
  - `honeypot_triggered`: 如果该节点是蜜罐，是否发生了任何交互 (布尔值)。

#### 2. 连接级策略条件 (Connection-level Conditions)
**场景**：当该特定链路 (Link) 承载的活动满足以下条件时触发。

- **链路负载 (Load)**:
  - `bandwidth_usage`: 链路带宽使用率百分比 (支持操作符后缀)。
  - `latency_ms`: 链路延迟 (毫秒，支持操作符后缀)。
- **协议活动 (Protocol)**:
  - `allowed_protocols`: 链路上允许运行的协议列表 (字符串数组)。
- **时间窗口 (Schedule)**:
  - `time_window`: 策略生效的特定时间段。包含 `start_time` (HH:MM), `end_time` (HH:MM) 和 `days` (周几，1-7)。
- **安全状态 (Security)**:
  - `anomaly_detected`: 链路两端节点间是否存在异常通信 (布尔值)。

#### 3. 流级策略条件 (Flow-level Conditions)
**场景**：当符合作用域定义的特定数据流 (Flow) 表现出以下特征时触发。

- **统计特征 (Stats)**:
  - `byte_rate`: 流的字节速率 (Bytes/s，支持操作符后缀)。
  - `duration`: 流的持续时间 (秒，支持操作符后缀)。
- **内容特征 (Content)**:
  - `function_code_entropy`: 功能码熵值 (0.0-1.0，支持操作符后缀)。
  - `payload_anomaly_score`: 载荷异常评分 (支持操作符后缀)。
- **状态判定 (Status)**:
  - `is_new_flow`: 是否为新建立的未知会话 (布尔值)。

### 动作定义 (Actions)
动作部分定义了当条件满足时要执行的操作。每个策略可以定义一个主要动作和多个次要动作。

#### 主要动作
主要动作是一个对象，包含以下字段：
- `action_type`: 动作类型 (字符串, 示例: "allow")
- `action_params`: 动作参数 (对象)

#### 主要动作类型（action_type）
- `allow`: 允许通过，不做阻断或降级处理。
- `block`: 立即拦截当前及后续流量/请求，不再转发；直接丢弃（不回复、不转发）。
- `throttle`: 限流/降速，按带宽或速率阈值进行限制。
- `disable`: 禁用目标对象（设备/连接/策略），未来新流量不允许建立；是配置层停用，需重新启用才恢复。
- `shutdown`（连接软切断）: 在有通知的前提下切断连接，先通知/收尾，再断开连接。
- `terminate`（连接硬切断）: 强制切断连接，立即断开不做收尾，用于应急。
- `redirect`: 将流量引导到新的目标（如蜜罐/隔离区），目标使用 IP+port；支持多目标数组时视为镜像到所有目标。
- `alert`: 生成告警，并添加到告警记录中

##### 主要动作参数要求
- `allow`: 无额外参数。
- `block`: 无额外参数。
- `throttle`: 
  - `rate_limit`: 需要对象，字段：
    - `bandwidth_mbps` (必填，>0，数值，Mbps，上限带宽)
    - `packets_per_second` (可选，>0，整数，包速率上限)
    - `direction` (可选，`ingress|egress|both`，默认 `both`)
    - `burst_packets` (可选，整数，突发包数上限，默认 0 表示不允许突发)
    - `burst_bytes` (可选，整数，突发字节上限，默认 0 表示不允许突发)
    - `strategy` (可选，`drop|queue`，超限行为，默认 `drop`)
    - `smoothing` (可选，`token_bucket|leaky_bucket`，默认 `token_bucket`)
- `disable`: 
  - `reason`: （字符串，可选）。
- `shutdown`: 
  - `notice`（字符串， 可选）。
- `terminate`: 无额外参数。
- `redirect`: 
  - `targets`: 支持单个或数组，形如 `{ "targets": [ { "ip": "10.0.0.99", "port": 502 } ] }`；多目标表示镜像到所有目标。
- `alert`: 
  - `alert_level`: 告警级别 (枚举: info/warning/high/critical, 示例: "high")

#### 次要动作
次要动作是一个对象，包含以下字段：
- `action_type`: 动作类型 (字符串, 示例: "log")
- `action_params`: 动作参数 (对象)

#### 次要动作类型（action_type）
次要动作通常用于补充主要动作，提供额外的功能：

- `log`: 日志记录 (对象)
- `alert`: 发送告警 (对象)
- `block`: 阻止特定协议或IP (对象)
- `redirect`: 重定向流量 (对象)
- `rate_limit`: 速率限制 (对象)

#### 次要动作参数要求
- `log`:
  - `log_level`: 日志级别 (枚举: info/warning/alert/error, 示例: "info")
  - `log_message`: 自定义日志消息 (字符串, 示例: "访问PLC-01")

- `alert`:
  - `alert_level`: 告警级别 (枚举: info/warning/high/critical, 示例: "high")

- `block`:
  - `blocked_protocols`: 被阻止的协议列表 (字符串数组, 示例: ["all_other"])

- `redirect`:
  - `redirect_target`: 重定向目标 (字符串, 如蜜罐标识符, 示例: "honeypot-01")

- `rate_limit`:
  - `bandwidth_mbps`: 带宽限制 (整数, Mbps, 示例: 10)


### 主要动作与次要动作的可选组合（互斥/允许）
- 当 `primary_action = allow`：可选次要动作 `log`、`alert`。不应叠加 `block`/`redirect`/`rate_limit`（语义冲突）。
- 当 `primary_action = block`：可选次要动作 `log`、`alert`。不要再叠加 `redirect` 或额外 `block`。
- 当 `primary_action = throttle`：必须有 `rate_limit`；可选 `log`、`alert`；不叠加 `block`/`redirect`。
- 当 `primary_action = disable` / `shutdown` / `terminate`：可选 `log`、`alert`；不叠加 `redirect`、`rate_limit`、`block`。
- 当 `primary_action = redirect`：可选 `redirect`（用于指定目标）、`log`、`alert`；不叠加 `block`/`rate_limit`。
- 当 `primary_action = alert`：可选 `log`；避免再叠加 `block`/`redirect`/`rate_limit`（保持告警语义单一）。

### 条件与动作的关系
条件和动作之间的关系决定了策略的行为逻辑：

1. **条件评估**: 系统持续监控策略作用域内的对象，当对象的状态满足策略定义的所有条件时，触发动作执行。

2. **动作执行**: 当条件被满足时，系统首先执行主要动作，然后按顺序执行所有次要动作；若主要动作或次要动作执行失败，不再做额外处理。

3. **条件组合**: 多个条件之间是AND关系，即必须同时满足所有条件才会触发动作。

4. **优先级处理**: 当多个策略同时匹配同一对象时，先按 `priority`（数值越小优先级越高）排序；若 `priority` 相同，则按创建时间，创建时间更新（更新近）者优先执行。

### 作用域定义 (Scope)
作用域定义了策略的应用范围，**必须与策略 `type` 对齐**：

- 当 `type = node`：
  - `target_type` 只能取：`device`
  - `target_identifier`: 设备标识（节点 ID/名称），如 `"PLC-01"`

- 当 `type = connection`：
  - `target_type` 只能取：`connection`
  - `target_identifier`: 连接标识（如链路 ID），如 `"conn-plc-hmi"`

- 当 `type = flow`：
  - `target_type` 可取：`protocol` | `ip_range` | `device`
    - `protocol`: 协议名，如 `"modbus"`、`"http"`
    - `ip_range`: CIDR，如 `"192.168.1.0/24"`
    - `device`: 作为端点的设备标识，如 `"PLC-01"`（表示以该设备为源或目的的流）
  - `target_identifier`: 与所选 `target_type` 对应的具体值

## 节点级策略

节点级策略以网络节点（如PLC、蜜罐等）为操作对象，控制节点的行为和访问权限。

### 1. 访问控制策略

控制对节点的访问权限。

示例：
```json
{
  "policy": {
    "id": "node-access-001",
    "name": "PLC-Access-Control",
    "description": "限制对PLC-01的访问",
    "type": "node",
    "subtype": "access_control",
    "status": "active",
    "priority": 100,
    "scope": {
      "target_type": "device",
      "target_identifier": "PLC-01"
    },
    "conditions": {
      "ingress_filter": {
        "src_ip": "192.168.1.10",
        "protocol": "modbus"
      },
      "anomaly_detected": false
    },
    "actions": {
      "primary_action": {
        "action_type": "allow"
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "info",
            "log_message": "访问PLC-01"
          }
        }
      ]
    }
  }
}
```

### 2. 资源保护策略

监控节点资源使用情况，防止资源耗尽。

示例：
```json
{
  "policy": {
    "id": "node-resource-001",
    "name": "PLC-Resource-Protection",
    "description": "监控PLC-01资源使用情况",
    "type": "node",
    "subtype": "resource_protection",
    "status": "active",
    "priority": 200,
    "scope": {
      "target_type": "device",
      "target_identifier": "PLC-01"
    },
    "conditions": {
      "cpu_usage_gte": 85,
      "mem_usage_gte": 90
    },
    "actions": {
      "primary_action": {
        "action_type": "alert",
        "action_params": {
          "alert_level": "high",
          "notification_channels": ["email", "syslog"]
        }
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "warning",
            "log_message": "PLC-01资源使用率过高"
          }
        }
      ]
    }
  }
}
```

### 3. 服务启停策略

根据条件自动启停节点服务。

示例：
```json
{
  "policy": {
    "id": "node-service-001",
    "name": "PLC-Auto-Shutdown",
    "description": "在检测到异常时自动关闭PLC服务",
    "type": "node",
    "subtype": "service_control",
    "status": "active",
    "priority": 150,
    "scope": {
      "target_type": "device",
      "target_identifier": "PLC-01"
    },
    "conditions": {
      "anomaly_detected": true
    },
    "actions": {
      "primary_action": {
        "action_type": "shutdown",
        "action_params": {}
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "alert",
            "log_message": "检测到异常，关闭PLC服务"
          }
        },
        {
          "action_type": "alert",
          "action_params": {
            "alert_level": "critical",
            "notification_channels": ["email", "syslog"]
          }
        }
      ]
    }
  }
}
```

### 4. 蜜罐诱捕策略

当蜜罐节点被触发时，记录并告警。

示例：
```json
{
  "policy": {
    "id": "node-honeypot-001",
    "name": "Honeypot-Trigger-Alert",
    "description": "蜜罐节点触发告警",
    "type": "node",
    "subtype": "honeypot_trap",
    "status": "active",
    "priority": 10,
    "scope": {
      "target_type": "device",
      "target_identifier": "Honeypot-01"
    },
    "conditions": {
      "honeypot_triggered": true
    },
    "actions": {
      "primary_action": {
        "action_type": "alert",
        "action_params": {
          "alert_level": "critical"
        }
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "alert",
            "log_message": "检测到对蜜罐节点的非法访问"
          }
        }
      ]
    }
  }
}
```

## 连接级策略

连接级策略控制节点间的通信连接。

### 1. 带宽控制策略

限制连接带宽，防止洪泛攻击。

示例：
```json
{
  "policy": {
    "id": "conn-bandwidth-001",
    "name": "Connection-Bandwidth-Limit",
    "description": "限制PLC与HMI之间连接的带宽",
    "type": "connection",
    "subtype": "bandwidth_control",
    "status": "active",
    "priority": 100,
    "scope": {
      "target_type": "connection",
      "target_identifier": "conn-plc-hmi"
    },
    "conditions": {
      "bandwidth_usage_gt": 70,
      "time_window": {
        "start_time": "08:00",
        "end_time": "18:00",
        "days": [1, 2, 3, 4, 5]
      }
    },
    "actions": {
      "primary_action": {
        "action_type": "throttle",
        "action_params": {
          "rate_limit": {
            "bandwidth_mbps": 10
          }
        }
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "info",
            "log_message": "限制PLC-HMI连接带宽至10Mbps"
          }
        }
      ]
    }
  }
}
```

### 2. 连接状态策略

根据条件自动启用或禁用连接。

示例：
```json
{
  "policy": {
    "id": "conn-state-001",
    "name": "Connection-Anomaly-Disable",
    "description": "检测到异常时禁用连接",
    "type": "connection",
    "subtype": "state_control",
    "status": "active",
    "priority": 50,
    "scope": {
      "target_type": "connection",
      "target_identifier": "conn-plc-hmi"
    },
    "conditions": {
      "anomaly_detected": true
    },
    "actions": {
      "primary_action": {
        "action_type": "disable",
        "action_params": {}
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "alert",
            "log_message": "检测到异常，禁用PLC-HMI连接"
          }
        }
      ]
    }
  }
}
```

### 3. 协议过滤策略

控制连接上允许的协议类型。

示例：
```json
{
  "policy": {
    "id": "conn-protocol-001",
    "name": "Modbus-Protocol-Filter",
    "description": "只允许Modbus协议通过PLC连接",
    "type": "connection",
    "subtype": "protocol_filter",
    "status": "active",
    "priority": 200,
    "scope": {
      "target_type": "connection",
      "target_identifier": "conn-plc-switch"
    },
    "conditions": {
      "allowed_protocols": ["modbus"]
    },
    "actions": {
      "primary_action": {
        "action_type": "allow",
        "action_params": {}
      },
      "secondary_actions": [
        {
          "action_type": "block",
          "action_params": {
            "blocked_protocols": ["all_other"]
          }
        },
        {
          "action_type": "log",
          "action_params": {
            "log_level": "info",
            "log_message": "只允许Modbus协议通过"
          }
        }
      ]
    }
  }
}
```

## 流级策略

流级策略针对具体的数据流进行精细化控制。

### 1. 异常流量阻断策略

当流特征超出阈值时自动阻断。

示例：
```json
{
  "policy": {
    "id": "flow-block-001",
    "name": "High-Entropy-Traffic-Block",
    "description": "阻断高熵值的Modbus流量",
    "type": "flow",
    "subtype": "anomaly_blocking",
    "status": "active",
    "priority": 50,
    "scope": {
      "target_type": "protocol",
      "target_identifier": "modbus"
    },
    "conditions": {
      "function_code_entropy_gt": 0.8,
      "byte_rate_gt": 10000
    },
    "actions": {
      "primary_action": {
        "action_type": "block",
        "action_params": {}
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "alert",
            "log_message": "阻断高熵值Modbus流量"
          }
        },
        {
          "action_type": "alert",
          "action_params": {
            "alert_level": "high",
            "notification_channels": ["syslog"]
          }
        }
      ]
    }
  }
}
```

### 2. 流量重定向策略

将可疑流量重定向至蜜罐。

示例：
```json
{
  "policy": {
    "id": "flow-redirect-001",
    "name": "Suspicious-Traffic-Redirect",
    "description": "将可疑流量重定向至蜜罐",
    "type": "flow",
    "subtype": "traffic_redirect",
    "status": "active",
    "priority": 75,
    "scope": {
      "target_type": "ip_range",
      "target_identifier": "192.168.1.0/24"
    },
    "conditions": {
      "payload_anomaly_score_gt": 0.9
    },
    "actions": {
      "primary_action": {
        "action_type": "redirect",
        "action_params": {
          "targets": [
            { "ip": "10.0.0.99", "port": 502 }
          ]
        }
      },
      "secondary_actions": [
        {
          "action_type": "redirect",
          "action_params": {
            "redirect_target": "honeypot-01"
          }
        },
        {
          "action_type": "log",
          "action_params": {
            "log_level": "info",
            "log_message": "重定向可疑流量至蜜罐"
          }
        }
      ]
    }
  }
}
```

### 3. 会话控制策略

控制流的最大持续时间和数据量。

示例：
```json
{
  "policy": {
    "id": "flow-session-001",
    "name": "Session-Duration-Control",
    "description": "限制Modbus会话最大持续时间",
    "type": "flow",
    "subtype": "session_control",
    "status": "active",
    "priority": 150,
    "scope": {
      "target_type": "protocol",
      "target_identifier": "modbus"
    },
    "conditions": {
      "duration_gt": 3600
    },
    "actions": {
      "primary_action": {
        "action_type": "terminate",
        "action_params": {}
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "action_params": {
            "log_level": "info",
            "log_message": "终止超时的Modbus会话"
          }
        }
      ]
    }
  }
}
```

## 策略操作说明

每种策略都支持以下基本操作：
1. **创建** - 定义新的策略规则
2. **应用** - 将策略应用到目标对象（节点、连接或流）
3. **撤销** - 取消策略在目标对象上的应用
4. **更新** - 修改策略的配置参数
5. **删除** - 移除不再需要的策略

策略的执行遵循优先级原则，优先级数字越小的策略越先执行。当多个策略同时匹配同一个对象时，系统会按照优先级顺序依次应用策略。