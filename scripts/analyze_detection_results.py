import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import create_app
from src.app.db import session_scope
from src.app.db.models import AppFlow

def analyze_results():
    # Disable flask logging
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    # Disable controller WS to avoid starting threads
    os.environ["ENABLE_CONTROLLER_WS"] = "False"
    
    app = create_app()
    with app.app_context():
        with session_scope() as session:
            # Query top rate flows
            flows = session.query(AppFlow).order_by(AppFlow.pkt_rate.desc()).limit(20).all()

            if not flows:
                print("No flows found.")
                return

            print(f"Top {len(flows)} flows by Packet Rate:")
            data = []
            for f in flows:
                data.append({
                    "Flow ID": f.flow_id,
                    "Src IP": f.src_ip,
                    "Pkt Rate": f.pkt_rate,
                    "Entropy": f.func_code_entropy,
                    "Reg Std": f.reg_addr_std,
                    "Decision": f.decision_level,
                    "Prob": f.prob,
                    "Status": f.detect_status
                })

            df = pd.DataFrame(data)
            print(df.to_string(index=False))

            # Analyze the first one in detail if exists
            if flows:
                print("\n--- Detailed Analysis of Most Recent Abnormal Flow ---")
                f = flows[0]
                print(f"Flow ID: {f.flow_id}")
                print(f"Source: {f.src_ip}:{f.src_port} -> {f.dst_ip}:{f.dst_port}")
                print(f"Protocol: {f.protocol}")
                print(f"Stats: {f.pkt_count} pkts, {f.byte_count} bytes, {f.duration}s")
                print(f"Rates: {f.pkt_rate:.2f} pkt/s, {f.byte_rate:.2f} byte/s")
                print(f"Modbus Features: Entropy={f.func_code_entropy}, RegStd={f.reg_addr_std}")
                print(f"Detection: {f.decision_level} (Prob: {f.prob:.4f})")
                print(f"Status: {f.detect_status}")
                
                # Check heuristic logic match
                avg_pkt_size = 0
                if f.pkt_count and f.pkt_count > 0:
                    avg_pkt_size = f.byte_count / f.pkt_count
                
                print(f"Avg Pkt Size: {avg_pkt_size:.2f} bytes")
                
                if f.pkt_rate and f.pkt_rate > 1000 and avg_pkt_size < 120:
                    print(">> Matches Heuristic Logic for SYN Flood (High Rate, Small Packets)")
                elif f.pkt_rate and f.pkt_rate < 5.0:
                     print(">> Low Rate Flow (< 5.0 pkt/s)")
                     if (f.func_code_entropy is None or f.func_code_entropy < 0.1) and (f.reg_addr_std is None or f.reg_addr_std < 5.0):
                         print("   -> Should be WHITELISTED (Low Entropy & Low Std)")
                     else:
                         print("   -> Suspicious Low Rate (High Entropy or High Std) - Correctly NOT whitelisted")
                else:
                    print(">> Does NOT match Heuristic Logic directly (Check model features)")

if __name__ == "__main__":
    analyze_results()
