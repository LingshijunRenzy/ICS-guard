#!/usr/bin/env python3
"""
训练 LightGBM 流量检测模型：
- 输入：datasets/ICS-flow/archive/Dataset.csv（可通过 --data-path 覆盖）
- 输出：
  models/YYMMDD_HHMMSS_lightgbm_model.pkl
  models/YYMMDD_HHMMSS_features.json（特征列顺序）
  models/YYMMDD_HHMMSS_thresholds.json（推理阈值）
  models/YYMMDD_HHMMSS_metrics.png（训练/验证指标可视化）
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import joblib
import lightgbm as lgb
import matplotlib
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

# 使用无界面后端以便脚本运行在服务器/CI
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from prepare_ics_flow import build_training_xy, load_raw_ics_flow


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "datasets" / "ICS-flow" / "archive" / "Dataset.csv"
DEFAULT_OUTPUT_DIR = ROOT / "models"


def _prepare_xy(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    构建训练特征与标签，保持与 prepare_ics_flow 一致的预处理。
    - 标签映射：
      * 若标签为数值：0 视为 Normal，其余视为 Attack
      * 若标签为字符串：忽略大小写，"normal" 视为 Normal，其余视为 Attack
    - 特征：仅使用数值列，缺失填充为 0
    """
    X_raw, y_raw = build_training_xy(df)

    if y_raw.dtype != object:
        y = (y_raw != 0).astype(int)
    else:
        y = (y_raw.astype(str).str.lower() != "normal").astype(int)

    # 仅保留数值/布尔列，缺失填充 0
    feature_df = X_raw.select_dtypes(include=["number", "bool"]).copy()
    feature_df = feature_df.fillna(0)

    feature_names: List[str] = list(feature_df.columns)
    return feature_df, y, feature_names


def train_model(
    data_path: Path,
    output_dir: Path,
    test_size: float = 0.2,
    random_state: int = 42,
) -> None:
    df_raw = load_raw_ics_flow() if data_path == DEFAULT_DATA_PATH else pd.read_csv(data_path)
    df_raw = shuffle(df_raw, random_state=random_state)

    X, y, feature_names = _prepare_xy(df_raw)

    # 数据质量检查：确保存在正负样本
    class_counts = y.value_counts().to_dict()
    if y.nunique() < 2:
        raise ValueError(f"标签仅包含单一类别，无法训练二分类模型：{class_counts}")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = lgb.LGBMClassifier(
        n_estimators=800,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        max_depth=-1,
        objective="binary",
        class_weight="balanced",
        random_state=random_state,
        verbosity=-1,
    )

    model.fit(X_train, y_train)

    # 验证集指标
    val_probs = model.predict_proba(X_val)[:, 1]
    val_preds = (val_probs >= 0.5).astype(int)

    # 训练集指标（用于对比）
    train_probs = model.predict_proba(X_train)[:, 1]
    train_preds = (train_probs >= 0.5).astype(int)

    metrics = {
        "roc_auc": float(roc_auc_score(y_val, val_probs)),
        "f1": float(f1_score(y_val, val_preds)),
        "train_roc_auc": float(roc_auc_score(y_train, train_probs)),
        "train_f1": float(f1_score(y_train, train_preds)),
    }

    # 阈值可根据验证集后续调优，这里提供与应用层配置一致的初始值
    thresholds = {
        "alert": 0.3,
        "throttle": 0.6,
        "block": 0.8,
        "redirect": 0.9,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%y%m%d_%H%M%S_")
    model_path = output_dir / f"{timestamp}lightgbm_model.pkl"
    features_path = output_dir / f"{timestamp}features.json"
    thresholds_path = output_dir / f"{timestamp}thresholds.json"
    metrics_fig_path = output_dir / f"{timestamp}metrics.png"

    joblib.dump(model, model_path)

    with open(features_path, "w") as f:
        json.dump(feature_names, f, ensure_ascii=False, indent=2)

    with open(thresholds_path, "w") as f:
        json.dump(thresholds, f, ensure_ascii=False, indent=2)

    # 绘制训练/验证指标对比
    plt.figure(figsize=(6, 4))
    names = ["ROC-AUC", "F1"]
    train_vals = [metrics["train_roc_auc"], metrics["train_f1"]]
    val_vals = [metrics["roc_auc"], metrics["f1"]]
    x = range(len(names))
    plt.bar([i - 0.2 for i in x], train_vals, width=0.4, label="Train")
    plt.bar([i + 0.2 for i in x], val_vals, width=0.4, label="Validation")
    plt.xticks(list(x), names)
    plt.ylim(0, 1.0)
    plt.ylabel("Score")
    plt.title("LightGBM Metrics")
    plt.legend()
    plt.tight_layout()
    plt.savefig(metrics_fig_path, dpi=150)
    plt.close()

    print("Train samples:", len(X_train), "Val samples:", len(X_val))
    print("Metrics:", json.dumps(metrics, ensure_ascii=False, indent=2))
    print("Saved model to:", model_path)
    print("Saved features to:", features_path)
    print("Saved thresholds to:", thresholds_path)
    print("Saved metrics figure to:", metrics_fig_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LightGBM model for ICS-Guard.")
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH, help="Dataset CSV path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for model and metadata")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    train_model(args.data_path, args.output_dir, test_size=args.test_size, random_state=args.seed)


if __name__ == "__main__":
    main()

