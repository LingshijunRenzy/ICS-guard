# ICS-guard

基于 SDN 的工业控制网络智能流量监测与动态隔离系统。

## 项目简介

ICS-guard 是一个专为工业控制系统（ICS）设计的安全防护平台。它结合了软件定义网络（SDN）的灵活性与人工智能的检测能力，实现对工业协议（如 Modbus/TCP）流量的实时监控、异常检测以及自动化的威胁隔离。

## 技术栈

- **后端**: Python 3.11+, Flask, SQLAlchemy, Scapy, PyModbus, PyTorch/LightGBM (AI 推理)
- **前端**: Vue 3, Vite, TypeScript, Element Plus, Three.js (3D 拓扑可视化)
- **通信**: WebSocket (实时事件推送), REST API

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

### 开发调试 (Development)

在开发阶段，前端和后端独立运行，通过 Vite 代理进行联调。

1. **启动后端**:
   ```bash
   # 在项目根目录下
   python -m src.app.main
   ```
   后端默认运行在 `http://localhost:5000`。

2. **启动前端**:
   ```bash
   cd web-ui
   npm run dev
   ```
   前端默认运行在 `http://localhost:5173`。访问 `http://localhost:5173/ui/` 即可开始调试。Vite 已配置代理，会自动将 `/api` 和 `/ws` 请求转发至后端。

### 构建与部署 (Build & Production)

在生产环境下，前端被构建为静态文件并由 Flask 直接托管。

1. **构建前端**:
   ```bash
   cd web-ui
   npm run build
   ```
   构建产物将自动输出到 `src/app/static/` 目录下。

2. **运行集成应用**:
   ```bash
   # 在项目根目录下
   python -m src.app.main
   ```
   访问 `http://localhost:5000/ui` 即可访问完整集成的系统。

## 项目结构

- `src/app/`: Flask 后端核心逻辑
  - `api/`: RESTful 接口定义
  - `services/`: 核心业务逻辑（推理、流检测、事件订阅）
  - `static/`: 前端构建产物托管目录
- `web-ui/`: Vue 3 前端源码
- `models/`: 训练好的 AI 模型及阈值配置
- `scripts/`: 数据预处理与模型训练脚本
- `docs/`: 项目设计文档与 API 说明
- `datasets/`: 工业控制系统数据集（如 BATADAL, SWaT）
