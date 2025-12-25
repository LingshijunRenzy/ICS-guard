# ICS-Guard SDN Controller

基于 Ryu 开发的工业控制系统安全 SDN 控制器。

## 环境配置与运行指南

### 1. 系统要求
- 操作系统: Linux (推荐 Ubuntu 20.04/22.04)
- Python 版本: 3.8+
- Mininet: 2.3.0+

### 2. 安装依赖

#### 2.1 系统依赖
安装 Mininet 和 Open vSwitch：
```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch
```

#### 2.2 Python 依赖
建议使用虚拟环境：
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 运行控制器

在 `src/controller` 目录下运行：

```bash
# 启动 Ryu 控制器应用
# 注意：需要同时加载 sdn_controller.py (核心逻辑) 和 api.py (REST API)
ryu-manager sdn_controller.py --observe-links
```

控制器默认监听端口：
- OpenFlow: 6633 或 6653
- REST API: 8080 (Ryu 默认)

### 4. 运行 Mininet 仿真

在另一个终端窗口中，运行 Mininet 拓扑脚本：

```bash
# 进入 mininet 目录
cd mininet

# 清理旧环境（可选）
sudo mn -c

# 运行仿真拓扑
sudo python3 run.py
```

---

# Ryu SDN 控制器设计文档

## 1. 概述

本项目实现了一个基于 Ryu 框架的工业 SDN 控制器 (`controller/sdn_controller.py`)。该控制器专为具有环路冗余的工业网络拓扑设计，旨在解决广播风暴问题，并提供高效的最短路径转发能力。

## 2. 核心功能模块

控制器主要包含以下四个核心功能模块：

### 2.1 自动拓扑发现 (Topology Discovery)
*   **机制**: 利用 Ryu 的 `topology` 模块，通过 LLDP (Link Layer Discovery Protocol) 协议周期性地探测网络结构。
*   **实现**: 
    *   启动一个协程 `_discover_topology`，每隔 1 秒调用 `get_switch` 和 `get_link` API。
    *   构建基于 `networkx` 的无向图 `self.net`，实时维护交换机节点和链路连接关系。
    *   识别并记录“交换机间链路” (Inter-Switch Links)，以便区分主机端口和级联端口。

### 2.2 最小生成树 (MST) 计算与防环
*   **背景**: 工业网络为了高可靠性，通常采用双核心、双链路等冗余设计，这在二层网络中会形成物理环路，导致广播风暴。
*   **算法**: 使用 Prim 或 Kruskal 算法（通过 `networkx.minimum_spanning_tree`）在物理拓扑图上计算最小生成树。
*   **策略**: 
    *   对于**广播包** (如 ARP Request) 和**未知单播包**，控制器**仅允许其在 MST 包含的链路上转发**。
    *   逻辑上将有环的物理网络裁剪为无环的树状网络，从而彻底消除广播风暴。

### 2.3 智能泛洪 (Smart Flooding)
*   **逻辑**: 当收到需要泛洪的数据包时，控制器会动态计算输出端口列表：
    *   **主机端口**: 总是转发（假设主机不转发包，不会成环）。
    *   **交换机间端口**: 仅当该端口对应的链路属于当前的 MST 时才转发。
*   **优势**: 相比于传统的 STP (生成树协议) 禁用端口，SDN 控制器仅在处理广播流量时“逻辑禁用”链路，单播流量仍可使用所有物理链路。

### 2.4 最短路径转发 (Shortest Path Forwarding)
*   **机制**: 对于已知源和目的 MAC 地址的单播流量 (如 IPv4 Ping, TCP/UDP)。
*   **算法**: 使用 Dijkstra 算法 (`networkx.shortest_path`) 在**完整的物理拓扑图**（包含非 MST 链路）上计算最短路径。
*   **优势**: 充分利用冗余链路的带宽，实现负载均衡，避免流量全部拥堵在 MST 路径上。
*   **流表下发**: 计算出路径后，向沿途交换机下发高优先级 (`priority=1`) 的流表项，后续数据包直接由硬件转发，不再经过控制器。

## 3. 数据包处理流程 (Packet Processing Pipeline)

当控制器收到 `PacketIn` 消息时，处理流程如下：

1.  **解析与过滤**:
    *   解析 Ethernet 头部。
    *   **过滤 LLDP**: 忽略由拓扑发现模块产生的 LLDP 包。
    *   **过滤 IPv6 组播**: 忽略 `33:33:xx` 开头的 IPv6 NDP 包，减少干扰。
    *   **过滤 LLDP 组播**: 忽略 `01:80:c2:00:00:0e`。

2.  **主机位置学习**:
    *   如果数据包来自“非交换机间链路”（即连接主机的边缘端口），记录 `{MAC: (dpid, port)}` 映射关系。
    *   防止因环路导致的 MAC 地址漂移。

3.  **转发决策**:
    *   **情况 A: 目的 MAC 是广播地址 (ff:ff...) 或 未知地址**:
        *   执行 **MST 泛洪**。
        *   计算出端口：`[所有主机端口] + [MST 上的交换机端口] - [入端口]`。
        *   通过 `PacketOut` 发送数据包。
    *   **情况 B: 目的 MAC 已知**:
        *   执行 **最短路径转发**。
        *   计算从当前交换机到目的交换机的最短路径。
        *   确定下一跳端口。
        *   **下发流表**: `Match(src, dst, in_port) -> Action(Output)`。
        *   通过 `PacketOut` 发送当前数据包。

## 4. 关键数据结构

*   `self.net`: `networkx.Graph`，存储物理网络拓扑。
*   `self.links`: `dict`, `{(src_dpid, src_port): (dst_dpid, dst_port)}`，存储所有交换机间的互联信息。
*   `self.host_location`: `dict`, `{mac: (dpid, port)}`，存储主机接入位置。
*   `self.switch_ports`: `dict`, `{dpid: [port_list]}`，存储每个交换机的活动端口列表。

## 5. 依赖库
*   `ryu`: SDN 控制器框架。
*   `networkx`: 图论算法库，用于 MST 和最短路径计算。

