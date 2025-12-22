## Flow 特征映射（API 定义 ↔ ICS-Flow Dataset.csv）

本稿说明 **API 文档中的 `Flow` 数据结构** 与 `datasets/ICS-flow/archive/Dataset.csv` 之间的字段对应关系，作为后续特征工程和在线推理的数据契约基础。

API 中 `Flow` 的关键字段（摘自 `docs/api/README.md`，略去解释）：

- `id`: string
- `src_ip`: string
- `dst_ip`: string
- `src_port`: number
- `dst_port`: number
- `protocol`: string
- `start_time`: string
- `end_time`: string
- `duration`: number
- `pkt_count`: number
- `byte_count`: number
- `pkt_rate`: number
- `byte_rate`: number
- `func_code_entropy`: number
- `reg_addr_std`: number
- `status`: string

ICS-Flow `Dataset.csv` 的表头（节选）：

```text
sAddress,rAddress,sMACs,rMACs,sIPs,rIPs,protocol,
startDate,endDate,start,end,startOffset,endOffset,duration,
sPackets,rPackets,sBytesSum,rBytesSum,
...（多种统计/flags 特征）...,
IT_B_Label,IT_M_Label,NST_B_Label,NST_M_Label
```

### 1. 一一对应或简单变换即可得到的字段

- **`src_ip`** ← `sIPs`  
- **`dst_ip`** ← `rIPs`  
- **`protocol`** ← `protocol`（如 `IPV4-TCP`）  
- **`start_time`** ← `startDate`（字符串）或 `start`（UNIX 时间戳）  
- **`end_time`** ← `endDate` 或 `end`  
- **`duration`** ← `duration`  
- **`pkt_count`** ← `sPackets + rPackets`  
- **`byte_count`** ← `sBytesSum + rBytesSum`  
- **`pkt_rate`** ← `pkt_count / duration`（`duration>0` 时）  
- **`byte_rate`** ← `byte_count / duration`（`duration>0` 时）  
- **`status`** ← 由标签列映射而来，例如：
  - 选择 `IT_B_Label` 作为主标签列；
  - 若 `IT_B_Label == "Normal"` → `status = "normal"`；
  - 否则 `status = IT_B_Label`（直接使用攻击类型字符串）。

- **`id`**：ICS-Flow 未提供显式 ID，可在预处理阶段自生成，例如：
  - `id = 行号`；或  
  - `id = hash(src_ip, dst_ip, start_time, end_time, protocol, pkt_count)`。

### 2. 暂无直接来源的字段

- **`src_port` / `dst_port`**  
  - ICS-Flow 当前 CSV 中无显式端口字段。  
  - 处理策略（第一阶段）：
    - 训练与上线模型输入中**不依赖端口特征**；  
    - API 层的 `Flow` 结构可将端口设为 `null`/`0` 或标记为“未使用”；  
    - 如果未来基于 `traffic.pcap` + `ICSFlowGenerator` 重新生成带端口的 flow，再升级模型和映射。

- **`func_code_entropy` / `reg_addr_std`**  
  - 这些是对 Modbus/工控协议语义的特征，ICS-Flow 的公开 CSV 未包含。  
  - 第一阶段建议：
    - **不将其纳入模型输入**，在 API 中保留为扩展字段；  
    - 在线推理时可暂时置为 `null` / `0.0`，不参与策略判断；  
    - 等有自采工控流量并实现相应解析器后，再补充训练一版“带协议语义”的模型。

### 3. 训练用特征与线上输入的约定

在第一阶段的流级检测模型中：

- **训练/推理统一使用的基础字段**：
  - `src_ip`, `dst_ip`, `protocol`
  - `start_time`, `end_time`, `duration`
  - `pkt_count`, `byte_count`, `pkt_rate`, `byte_rate`
  - 以及 ICS-Flow 提供的其它统计特征（如各种 payload/flags/TTL/窗口等数值列）
- **不用作特征但在 API 中存在的字段**：
  - `src_port`, `dst_port`, `func_code_entropy`, `reg_addr_std`  
  - 暂时视为“占位/预留字段”，不进入当前模型特征向量。

这样可以保证：

- 训练数据（ICS-Flow）和在线输入（通过控制层实时提取的 `Flow`）在**使用的特征子集上保持同构**；  
- 同时又不强行依赖 ICS-Flow 中并不存在的信息，避免额外的离线重放/解析工程。


