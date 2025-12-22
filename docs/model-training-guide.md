## 模型训练指导（首版方案：主模型 LightGBM，Baseline MLP）

目标：基于 `datasets/ICS-flow/archive/Dataset.csv` 训练一个流级检测模型，用于判断 Normal/Attack（可扩展为多分类）。主模型用 LightGBM，Baseline 用浅层 MLP。

### 1. 数据准备
- 输入源：`datasets/ICS-flow/archive/Dataset.csv`（见 `scripts/prepare_ics_flow.py`）。
- 特征选择：
  - 保留数值统计特征（包/字节、速率、时序、flags、窗口等）。
  - 删除标签列：`IT_B_Label, IT_M_Label, NST_B_Label, NST_M_Label`。
  - 删除标识类列：`sIPs, rIPs, sMACs, rMACs, sAddress, rAddress`（端口/协议语义列缺失，第一版不使用）。
- 标签：
  - 二分类：使用 `IT_B_Label`，`Normal` → 0，其余攻击类型 → 1。
  - 多分类（可选）：直接使用 `IT_B_Label` 字符串类别。
- 缺失值：数值列可用 0 或均值填充；LightGBM 可原生处理缺失，MLP 需先填充。
- 划分：训练/验证（例如 80/20），注意按时间随机打乱或分层抽样。

### 2. 主模型：LightGBM
- 模型类型：`LGBMClassifier`
- 输入：标准化前的数值特征（无需缩放），类别特征需预先编码（若保留协议枚举，可 One-Hot）。
- 关键参数（建议起点，可通过 CV/Optuna 调优）：
  - `n_estimators`: 500–1500
  - `learning_rate`: 0.05–0.1
  - `max_depth`: -1 或 6–12
  - `num_leaves`: 31–255
  - `subsample`: 0.7–0.9
  - `colsample_bytree`: 0.7–0.9
  - `min_child_samples`: 20–100
  - `objective`: `binary` / `multiclass`
  - 类别不均衡：设置 `scale_pos_weight` 或使用 `class_weight="balanced"`
- 评价指标：
  - 二分类：AUC、F1、Precision@Recall、TNR@高 Recall。
  - 多分类：Macro-F1，或加权 F1。
- 输出与阈值：
  - 使用模型概率作为 `anomaly_score`；根据验证集设定 2–3 档阈值（例如 alert/block）。

### 3. Baseline：浅层 MLP
- 结构（示例）：
  - 输入：数值特征（先做标准化/归一化）
  - 隐层：2–3 层全连接（例如 256 → 128 → 64），激活 ReLU/GeLU
  - 正则：BatchNorm + Dropout(0.1–0.3)
  - 输出：Sigmoid（二分类）或 Softmax（多分类）
- 优化：
  - 损失：BCE / CrossEntropy
  - 优化器：AdamW lr=1e-3~3e-4，配合余弦或阶梯衰减
  - 批次：128–512；训练轮次：20–50，看验证集早停
- 评价与阈值：同 LightGBM，概率输出用于阈值设定。

### 4. 训练流程建议
1) 用 `scripts/prepare_ics_flow.py` 读取数据，获得特征/标签。
2) 划分训练/验证集（注意分层）。
3) 训练 LightGBM，保存模型与特征列顺序（用于线上一致性）。
4) 训练 MLP Baseline，对比验证集指标；如差距不大可保留 MLP 作为备用。
5) 在验证集上做阈值搜索，确定 `alert / throttle / block` 的分数门限。
6) 导出：模型文件（pkl/onnx）、特征列列表、阈值配置，写入应用层可读取的配置。

### 5. 部署对齐要点
- 在线特征应与训练时的列、顺序、预处理完全一致（删除 IP/MAC 等标识列；缺失填充策略一致）。
- 端口/工控协议语义字段当前缺失，API 中可保留为空，不作为模型输入。
- 输出对接：
  - `prob` → `anomaly_score`
  - `label`/`attack_type` → `status` 或 `alert.type`
  - 阈值 → 映射到策略动作（alert / throttle / block / isolate）

### 6. 后续迭代方向（可选）
- 短时序列：对流特征做时间窗聚合，尝试 1D-CNN/TCN。
- 无监督：训练 AE/DAE，仅用正常数据，重构误差做分数，再与监督模型分数组合。
- 端口/协议语义：若重新生成带端口和工控语义特征的 flow，再扩充输入维度重训。


