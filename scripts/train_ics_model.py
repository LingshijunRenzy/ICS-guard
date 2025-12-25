#!/usr/bin/env python3
"""
训练 LightGBM 流量检测模型（增强版）：
- 输入：datasets/processed/merged_training_data.csv
- 输出：
  models/YYMMDD_HHMMSS_lightgbm_model.pkl
  models/YYMMDD_HHMMSS_features.json
  models/YYMMDD_HHMMSS_thresholds.json
  models/YYMMDD_HHMMSS_metrics.png (指标对比)
  models/YYMMDD_HHMMSS_confusion_matrix.png (混淆矩阵热力图)
  models/YYMMDD_HHMMSS_feature_importance.png (特征重要性)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import joblib
import lightgbm as lgb
import matplotlib
import pandas as pd
import numpy as np
import seaborn as sns
from sklearn.metrics import f1_score, roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

# 使用无界面后端
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "datasets" / "processed" / "merged_training_data.csv"
DEFAULT_OUTPUT_DIR = ROOT / "models"

def _prepare_xy(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    从合并后的数据集中提取特征和标签。
    """
    # 标签列
    if 'IT_B_Label' in df.columns:
        y = df['IT_B_Label'].astype(int)
    else:
        # 兼容旧格式
        y = (df['IT_M_Label'].astype(str).str.lower() != "normal").astype(int)

    # 排除非特征列
    drop_cols = ['IT_B_Label', 'IT_M_Label', 'source', 'sAddress', 'rAddress', 'sMACs', 'rMACs', 'sIPs', 'rIPs', 'startDate', 'endDate', 'start', 'end']
    X = df.drop(columns=[c for c in drop_cols if c in df.columns])
    
    # 仅保留数值列
    X = X.select_dtypes(include=["number", "bool"]).copy()
    X = X.fillna(0)

    feature_names = list(X.columns)
    return X, y, feature_names

def plot_confusion_matrix(y_true, y_pred, path):
    plt.figure(figsize=(8, 6))
    cm = confusion_matrix(y_true, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False)
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.title('Confusion Matrix')
    plt.savefig(path, dpi=150)
    plt.close()

def plot_feature_importance(model, feature_names, path):
    plt.figure(figsize=(10, 8))
    importance = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values(by='importance', ascending=False).head(20)
    
    sns.barplot(x='importance', y='feature', data=importance)
    plt.title('Top 20 Feature Importance')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()

def train_model(
    data_path: Path,
    output_dir: Path,
    test_size: float = 0.2,
    random_state: int = 42,
    sample_frac: float = 1.0
) -> None:
    print(f"[*] Loading data from {data_path}...")
    # 使用 low_memory=False 避免警告
    df = pd.read_csv(data_path, low_memory=False)
    
    if sample_frac < 1.0:
        print(f"[*] Sampling {sample_frac*100}% of data...")
        df = df.sample(frac=sample_frac, random_state=random_state)
    
    df = shuffle(df, random_state=random_state)
    X, y, feature_names = _prepare_xy(df)
    
    print(f"[*] Dataset shape: {X.shape}, Features: {len(feature_names)}")
    print(f"[*] Class distribution: {y.value_counts().to_dict()}")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    print("[*] Training LightGBM model...")
    model = lgb.LGBMClassifier(
        n_estimators=1000,
        learning_rate=0.03,
        num_leaves=127,
        subsample=0.8,
        colsample_bytree=0.8,
        max_depth=-1,
        objective="binary",
        class_weight="balanced",
        random_state=random_state,
        verbosity=-1,
        n_jobs=-1
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric='binary_logloss',
        callbacks=[lgb.early_stopping(stopping_rounds=50)]
    )

    # 评估
    print("[*] Evaluating model...")
    val_probs = model.predict_proba(X_val)[:, 1]
    val_preds = (val_probs >= 0.5).astype(int)
    
    cm = confusion_matrix(y_val, val_preds)
    tn, fp, fn, tp = cm.ravel()
    
    metrics = {
        "roc_auc": float(roc_auc_score(y_val, val_probs)),
        "f1": float(f1_score(y_val, val_preds)),
        "precision": float(tp / (tp + fp)) if (tp + fp) > 0 else 0,
        "recall": float(tp / (tp + fn)) if (tp + fn) > 0 else 0,
    }
    
    print(f"[*] Metrics: {json.dumps(metrics, indent=2)}")

    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S_")
    
    model_path = output_dir / f"{timestamp}lightgbm_model.pkl"
    features_path = output_dir / f"{timestamp}features.json"
    thresholds_path = output_dir / f"{timestamp}thresholds.json"
    
    joblib.dump(model, model_path)
    with open(features_path, "w") as f:
        json.dump(feature_names, f, indent=2)
    
    # 默认阈值
    thresholds = {"alert": 0.3, "throttle": 0.6, "block": 0.8, "redirect": 0.9}
    with open(thresholds_path, "w") as f:
        json.dump(thresholds, f, indent=2)

    # 绘图
    print("[*] Generating plots...")
    plot_confusion_matrix(y_val, val_preds, output_dir / f"{timestamp}confusion_matrix.png")
    plot_feature_importance(model, feature_names, output_dir / f"{timestamp}feature_importance.png")
    
    # 指标柱状图
    plt.figure(figsize=(8, 5))
    m_names = list(metrics.keys())
    m_values = list(metrics.values())
    sns.barplot(x=m_names, y=m_values)
    plt.ylim(0, 1.1)
    plt.title('Model Performance Metrics')
    plt.savefig(output_dir / f"{timestamp}metrics.png", dpi=150)
    plt.close()

    print(f"[+] Training complete. Model saved to {model_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample", type=float, default=1.0, help="Fraction of data to use (0.0 to 1.0)")
    args = parser.parse_args()

    train_model(args.data_path, args.output_dir, sample_frac=args.sample)

if __name__ == "__main__":
    main()

