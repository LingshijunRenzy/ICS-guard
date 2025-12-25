# ICS-guard

基于 SDN 的工业控制网络智能流量监测与动态隔离系统。

## 项目简介

ICS-guard 是一个专为工业控制系统（ICS）设计的安全防护平台。它结合了软件定义网络（SDN）的灵活性与人工智能的检测能力，实现对工业协议（如 Modbus/TCP）流量的实时监控、异常检测以及自动化的威胁隔离。

## 技术栈

- **后端**: Python 3.11+, Flask, SQLAlchemy, Scapy, PyModbus, PyTorch/LightGBM (AI 推理)
- **前端**: Vue 3, Vite, TypeScript, Element Plus, Three.js (3D 拓扑可视化)
- **通信**: WebSocket (实时事件推送), REST API
- **SDN 控制器**: Ryu, Open vSwitch, Mininet

## 快速开始

### 环境准备

1. **后端环境**:
   ```bash
   # 创建并激活虚拟环境
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # venv\Scripts\activate  # Windows

   # 安装依赖
   pip install -r requirements.txt
   ```

2. **前端环境**:
   ```bash
   cd web-ui
   npm install
   ```

3. **控制器环境**:
   ```bash
   # 安装 Mininet 和 Open vSwitch
   sudo apt-get update
   sudo apt-get install -y mininet openvswitch-switch
   
   # 安装 Python 依赖 (建议在 venv 中)
   pip install -r src/controller/requirements.txt
   ```

### 启动流程

1. **启动 SDN 控制器**:
   在 `src/controller` 目录下运行：
   ```bash
   # 启动 Ryu 控制器应用
   ryu-manager sdn_controller.py --observe-links
   ```
   控制器默认监听端口：
   - OpenFlow: 6633 或 6653
   - REST API: 8080

2. **启动后端**:
   ```bash
   # 在项目根目录下
   python -m src.app.main
   ```
   后端默认运行在 `http://localhost:5000`。

3. **启动前端**:
   1. 在开发环境下运行：
   ```bash
   cd web-ui
   npm run dev
   ```
   前端默认运行在 `http://localhost:5173`。访问 `http://localhost:5173/ui/` 即可开始调试。
   2. 在生产环境下构建并托管：
   ```bash
   cd web-ui
   npm run build
   ```
   构建产物会生成在 `web-ui/dist/`，后端 Flask 会自动托管该目录下的静态文件, 通过localhost:5000/ui/访问。

4. **运行 Mininet 仿真 (可选)**:
   在另一个终端窗口中，运行 Mininet 拓扑脚本（需 root 权限）：
   ```bash
   sudo python src/controller/mininet/topo.py
   ```

## 系统架构与通信

系统由三部分组成，通过 REST API 和 WebSocket 进行通信：

1. **SDN 控制器 (Ryu)**:
   - 负责底层网络流量的转发、统计和策略执行。
   - 提供 REST API 供应用层查询拓扑、下发流表。
   - 通过 WebSocket (`/ws/events`) 向应用层推送实时流量事件（PacketIn, FlowStats）。

2. **应用层 (Flask)**:
   - **核心大脑**：接收控制器的流量数据，进行 AI 推理。
   - **API 服务**：为前端提供数据接口。
   - **事件总线**：订阅控制器的 WebSocket 事件，经过处理后通过自己的 WebSocket (`/ws/ui-events`) 推送给前端。

3. **前端 (Vue 3)**:
   - **可视化**：展示 3D 网络拓扑、实时流量监控。
   - **交互**：接收用户指令（如配置策略），调用应用层 API。
   - **实时通知**：监听应用层 WebSocket，弹出告警和状态更新。

## AI 检测与自动响应

### 数据集与处理
系统支持多种工业控制数据集进行模型训练，主要包括：
- **ICS-Flow**: 包含 ICS 网络流量与过程变量，提供正常/异常/攻击样本。
  - 来源: [ICS-Flow: An Industrial Control System Traffic Dataset for Intrusion Detection](https://arxiv.org/abs/2305.09678)
- **BoT-IoT**: 包含 IoT 网络中的 Botnet 流量，提供多种攻击场景。
  - 来源: [Towards the development of realistic botnet dataset in the internet of things for network forensic analytics: Bot-iot dataset](https://research.unsw.edu.au/projects/bot-iot-dataset)
- **UNSW-NB15**: 包含现代网络流量的综合数据集，涵盖正常与攻击行为。
  - 来源: [UNSW-NB15: a comprehensive data set for network intrusion detection systems](https://research.unsw.edu.au/projects/unsw-nb15-dataset)

**特征处理**:
系统从原始流量中提取以下关键特征用于推理：
- `duration`: 流持续时间
- `pkt_count`: 包数量
- `byte_count`: 字节总数
- `pkt_rate`: 发包速率
- `byte_rate`: 字节速率
- `sSynRate`: SYN 包占比（启发式填充）

### 安全判定逻辑
为了减少误报，系统内置了**智能白名单机制**。满足以下条件时，流量默认被视为**安全**：
1. **低频且规律**：流量速率极低 (`pkt_rate < 5.0`)，且表现出单纯的轮询特征（功能码熵低 `func_entropy < 0.1`，寄存器地址离散度低 `reg_std < 5.0`）。
2. **数据不足**：控制器尚未收集到足够的统计信息（`pkt_count` 缺失），且流量速率不高。

### 自动响应机制
当 AI 模型检测到高危流量（`DecisionLevel.BLOCK` 或 `DecisionLevel.REDIRECT`）时，系统会自动生成并下发策略：

1. **重定向 (Redirect)**:
   - 如果检测结果建议重定向，且网络拓扑中存在 **Honeypot (蜜罐)** 节点。
   - 系统会自动创建策略，将该恶意流的流量重定向到蜜罐 IP。
   
2. **阻断 (Block)**:
   - 如果检测结果建议阻断，或者建议重定向但网络中没有蜜罐。
   - 系统会创建高优先级的 DROP 策略，直接在交换机层面丢弃该流量。

3. **通知**:
   - 所有的自动响应动作都会生成 `traffic_block` 或 `traffic_redirect` 事件，实时推送到前端界面通知管理员。

## 项目结构

- `src/app/`: Flask 后端核心逻辑
  - `api/`: RESTful 接口定义
  - `services/`: 核心业务逻辑（推理、流检测、事件订阅）
  - `static/`: 前端构建产物托管目录
- `src/controller/`: SDN 控制器逻辑 (Ryu)
- `web-ui/`: Vue 3 前端源码
- `models/`: 训练好的 AI 模型及阈值配置
- `scripts/`: 数据预处理与模型训练脚本
- `docs/`: 项目设计文档与 API 说明
- `datasets/`: 工业控制系统数据集
