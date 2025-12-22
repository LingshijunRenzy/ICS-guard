# 数据集来源与下载

本项目实验可使用以下 ICS 相关数据集。以下链接均已手动打开验证可访问；若需下载原始压缩包，按各源要求（Kaggle 账号或官网申请）获取。

## ICS-Flow
- 简介：含 ICS 网络流量与过程变量，提供正常/异常/攻击样本，适合监督和无监督训练。
- 官方论文页（可访问，含数据说明）：https://arxiv.org/abs/2305.09678
- Kaggle 镜像（需登录）：https://www.kaggle.com/datasets/alirezadehlaghi/ics-flow-dataset

## SWaT (Secure Water Treatment)
- 简介：水处理试验台的传感器/执行器数据，含正常与多阶段攻击。
- 官方信息页（需在线申请下载权限）：https://itrust.sutd.edu.sg/itrust-labs_datasets/dataset_info/
- Kaggle 镜像（需登录）：https://www.kaggle.com/datasets/vishala28/swat-dataset-secure-water-treatment-system

## BATADAL
- 简介：供水系统数据，含正常与攻击场景，用于攻击检测竞赛。
- 官方数据页（含 Training/Test 数据集直链）：https://www.batadal.net/data.html
- Kaggle 镜像（需登录）：https://www.kaggle.com/datasets/icsdataset/batadal

## Kaggle API 快速使用
1) 安装：`pip install kaggle`  
2) 放置密钥：将 `kaggle.json` 置于 `~/.kaggle/`，权限 600。  
3) 下载示例：在目标目录执行上述 Kaggle CLI 命令；下载后解压 `unzip <file>.zip -d <target_dir>`。  

