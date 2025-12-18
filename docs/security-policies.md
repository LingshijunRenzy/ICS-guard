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

### 条件定义 (Conditions)
条件部分定义了策略触发所需满足的条件。不同类型的策略支持不同的条件字段：

#### 节点级策略条件
- `allowed_ips`: 允许访问的IP地址列表 (字符串数组, 示例: ["192.168.1.10", "192.168.1.20"])
- `denied_ips`: 拒绝访问的IP地址列表 (字符串数组, 示例: ["192.168.1.30"])
- `trigger_thresholds`: 触发阈值设置 (对象)
  - `cpu_usage_percent`: CPU使用率百分比阈值 (整数, 0-100, 示例: 80)
  - `memory_usage_percent`: 内存使用率百分值阈值 (整数, 0-100, 示例: 85)
- `anomaly_detected`: 是否检测到异常 (布尔值, 示例: true)

#### 连接级策略条件
- `allowed_protocols`: 允许的协议列表 (字符串数组, 示例: ["modbus", "http"])
- `time_window`: 时间窗口 (对象)
  - `start_time`: 开始时间 (字符串, HH:MM格式, 示例: "08:00")
  - `end_time`: 结束时间 (字符串, HH:MM格式, 示例: "18:00")
- `anomaly_detected`: 是否检测到异常 (布尔值, 示例: false)

#### 流级策略条件
- `trigger_thresholds`: 触发阈值设置 (对象)
  - `function_code_entropy`: 功能码熵值阈值 (浮点数, 0.0-1.0, 示例: 0.8)
  - `duration_seconds`: 会话持续时间阈值（秒）(整数, 示例: 3600)
- `suspicion_level`: 怀疑级别 (枚举: low/medium/high, 示例: "high")

### 动作定义 (Actions)
动作部分定义了当条件满足时要执行的操作。每个策略可以定义一个主要动作和多个次要动作。

#### 主要动作类型 (字符串)
- `allow`: 允许操作
- `block`: 阻止操作
- `throttle`: 限流操作
- `disable`: 禁用操作
- `shutdown`: 关闭操作
- `terminate`: 终止操作
- `redirect`: 重定向操作
- `alert`: 告警操作

示例: "allow"

#### 次要动作类型
次要动作通常用于补充主要动作，提供额外的功能：

- `log`: 日志记录 (对象)
  - `log_level`: 日志级别 (枚举: info/warning/alert/error, 示例: "info")
  - `log_message`: 自定义日志消息 (字符串, 示例: "访问PLC-01")

- `alert`: 发送告警 (对象)
  - `alert_level`: 告警级别 (枚举: info/warning/high/critical, 示例: "high")
  - `notification_channels`: 通知渠道 (字符串数组, 示例: ["email", "syslog"])

- `block`: 阻止特定协议或IP (对象)
  - `blocked_protocols`: 被阻止的协议列表 (字符串数组, 示例: ["all_other"])

- `redirect`: 重定向流量 (对象)
  - `redirect_target`: 重定向目标 (字符串, 如蜜罐标识符, 示例: "honeypot-01")

- `rate_limit`: 速率限制 (对象)
  - `bandwidth_mbps`: 带宽限制 (整数, Mbps, 示例: 10)

### 条件与动作的关系
条件和动作之间的关系决定了策略的行为逻辑：

1. **条件评估**: 系统持续监控策略作用域内的对象，当对象的状态满足策略定义的所有条件时，触发动作执行。

2. **动作执行**: 当条件被满足时，系统首先执行主要动作，然后按顺序执行所有次要动作。

3. **条件组合**: 多个条件之间是AND关系，即必须同时满足所有条件才会触发动作。

4. **优先级处理**: 当多个策略同时匹配同一对象时，系统按照优先级顺序执行，优先级高的策略先执行。

### 作用域定义 (Scope)
作用域定义了策略的应用范围：
- `target_type`: 目标类型 (枚举: device/connection/protocol/ip_range, 示例: "device")
- `target_identifier`: 目标标识符 (字符串, 具体设备名、连接标识、协议名或IP段, 示例: "PLC-01")

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
      "allowed_ips": ["192.168.1.10", "192.168.1.20"],
      "denied_ips": ["192.168.1.30"]
    },
    "actions": {
      "primary_action": "allow",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "info",
          "log_message": "访问PLC-01"
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
      "trigger_thresholds": {
        "cpu_usage_percent": 80,
        "memory_usage_percent": 85
      }
    },
    "actions": {
      "primary_action": "alert",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "warning",
          "log_message": "PLC-01资源使用率过高"
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
      "primary_action": "shutdown",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "alert",
          "log_message": "检测到异常，关闭PLC服务"
        },
        {
          "action_type": "alert",
          "alert_level": "critical",
          "notification_channels": ["email", "syslog"]
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
      "time_window": {
        "start_time": "08:00",
        "end_time": "18:00"
      }
    },
    "actions": {
      "primary_action": "throttle",
      "rate_limit": {
        "bandwidth_mbps": 10
      },
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "info",
          "log_message": "限制PLC-HMI连接带宽至10Mbps"
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
      "primary_action": "disable",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "alert",
          "log_message": "检测到异常，禁用PLC-HMI连接"
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
      "primary_action": "allow",
      "secondary_actions": [
        {
          "action_type": "block",
          "blocked_protocols": ["all_other"]
        },
        {
          "action_type": "log",
          "log_level": "info",
          "log_message": "只允许Modbus协议通过"
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
      "trigger_thresholds": {
        "function_code_entropy": 0.8
      }
    },
    "actions": {
      "primary_action": "block",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "alert",
          "log_message": "阻断高熵值Modbus流量"
        },
        {
          "action_type": "alert",
          "alert_level": "high",
          "notification_channels": ["syslog"]
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
      "suspicion_level": "high"
    },
    "actions": {
      "primary_action": "redirect",
      "secondary_actions": [
        {
          "action_type": "redirect",
          "redirect_target": "honeypot-01"
        },
        {
          "action_type": "log",
          "log_level": "info",
          "log_message": "重定向可疑流量至蜜罐"
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
      "trigger_thresholds": {
        "duration_seconds": 3600
      }
    },
    "actions": {
      "primary_action": "terminate",
      "secondary_actions": [
        {
          "action_type": "log",
          "log_level": "info",
          "log_message": "终止超时的Modbus会话"
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