"""
草稿：从 ICS-Flow Dataset.csv 生成与 API Flow 结构对齐的训练数据.

约定:
- 输入: datasets/ICS-flow/archive/Dataset.csv
- 输出:
  1) 一个对齐 API Flow 关键字段的 DataFrame
  2) X, y 训练矩阵 (以 IT_B_Label 为主标签, Normal vs Attack / 多分类均可)

本脚本仅做结构演示, 不负责模型训练.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "datasets" / "ICS-flow" / "archive" / "Dataset.csv"


def load_raw_ics_flow() -> pd.DataFrame:
    """加载原始 ICS-Flow Dataset.csv."""
    df = pd.read_csv(DATASET_PATH)
    return df


def build_flow_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    将原始 ICS-Flow 字段映射为与 API Flow 结构对齐的一张表.

    只构建目前可以可靠填充的字段; 端口/协议语义特征暂不填.
    """
    flow = pd.DataFrame()

    # 生成 id
    flow["id"] = df.reset_index().index.astype(str)

    # IP 与协议
    flow["src_ip"] = df.get("sIPs")
    flow["dst_ip"] = df.get("rIPs")
    flow["protocol"] = df.get("protocol")

    # 时间戳与时长
    flow["start_time"] = df.get("startDate")
    flow["end_time"] = df.get("endDate")
    flow["duration"] = df.get("duration")

    # 包/字节计数与速率
    s_pkts = df.get("sPackets")
    r_pkts = df.get("rPackets")
    s_bytes = df.get("sBytesSum")
    r_bytes = df.get("rBytesSum")

    pkt_count = s_pkts.fillna(0) + r_pkts.fillna(0)
    byte_count = s_bytes.fillna(0) + r_bytes.fillna(0)

    flow["pkt_count"] = pkt_count
    flow["byte_count"] = byte_count

    duration = flow["duration"].replace(0, pd.NA)
    flow["pkt_rate"] = pkt_count / duration
    flow["byte_rate"] = byte_count / duration

    # 状态: 使用 IT_B_Label, Normal 保留, 其它直接用攻击类型字符串
    label_series = df.get("IT_B_Label")
    status = label_series.copy()
    flow["status"] = status

    # 预留字段: 目前无可靠来源, 统一置为缺失值
    flow["src_port"] = pd.NA
    flow["dst_port"] = pd.NA
    flow["func_code_entropy"] = pd.NA
    flow["reg_addr_std"] = pd.NA

    return flow


def build_training_xy(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    基于原始 ICS-Flow 构建训练特征 X 与标签 y.

    约定:
    - y: 来自 IT_B_Label
      - 二分类: Normal vs 非 Normal (可在后处理时再合并)
      - 多分类: 直接使用字符串类别
    - X: 去掉显式标签列与明显的标识符列, 保留数值统计特征.
    """
    label_col = "IT_B_Label"
    y = df[label_col].copy()

    drop_cols = {
        # 明显标签列
        "IT_B_Label",
        "IT_M_Label",
        "NST_B_Label",
        "NST_M_Label",
        # 标识符/冗余信息
        "sMACs",
        "rMACs",
        "sIPs",
        "rIPs",
        "sAddress",
        "rAddress",
    }
    existing_drop = [c for c in df.columns if c in drop_cols]
    X = df.drop(columns=existing_drop)

    return X, y


def main() -> None:
    df_raw = load_raw_ics_flow()

    flow_table = build_flow_table(df_raw)
    print("Flow table preview:")
    print(flow_table.head())

    X, y = build_training_xy(df_raw)
    print("\nTraining features shape:", X.shape)
    print("Training labels distribution:")
    print(y.value_counts())


if __name__ == "__main__":
    main()


