import pandas as pd
import numpy as np

DATA_PATH = "datasets/processed/merged_training_data.csv"

def verify_data():
    print(f"[*] Reading {DATA_PATH}...")
    # Read a chunk to avoid memory issues if the file is huge, but 700MB fits in memory usually.
    # Let's read full file to be sure about distribution, or a large chunk.
    # Given the environment, let's read the first 100k rows and then sample if needed, 
    # or just read the whole thing if we are confident. 
    # Let's read 500,000 rows to be safe and fast.
    df = pd.read_csv(DATA_PATH, nrows=500000)
    
    print(f"[*] Loaded {len(df)} rows for verification.")
    
    # 1. Check for NaNs
    nan_counts = df.isna().sum()
    if nan_counts.sum() > 0:
        print("[!] Found missing values:")
        print(nan_counts[nan_counts > 0])
    else:
        print("[+] No missing values found.")
        
    # 2. Check Data Types
    print("\n[*] Data Types:")
    print(df.dtypes)
    
    # 3. Check Label Distribution
    print("\n[*] Label Distribution (Sample):")
    print(df['IT_M_Label'].value_counts())
    
    # 4. Check High Rate Samples
    high_rate = df[df['pkt_rate'] > 10000]
    print(f"\n[*] Samples with pkt_rate > 10000: {len(high_rate)}")
    if len(high_rate) > 0:
        print(high_rate[['pkt_rate', 'sSynRate', 'IT_M_Label']].head())
        
    # 5. Check SYN Rate in Attacks
    attacks = df[df['IT_B_Label'] == 1]
    if len(attacks) > 0:
        avg_syn = attacks['sSynRate'].mean()
        print(f"\n[*] Average sSynRate in Attacks: {avg_syn:.4f}")
        
    print("\n[*] Verification Complete.")

if __name__ == "__main__":
    verify_data()
