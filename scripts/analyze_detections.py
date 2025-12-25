
import sys
import os
import json
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append('/home/lingshi/coding/ICS-guard/src')

from app.db import session_scope
from app.db.models import FlowDetectionLog, AppFlow

def analyze_recent_detections():
    now = datetime.now(timezone.utc)
    thirty_seconds_ago = now - timedelta(seconds=30)
    
    print(f"Analyzing detections since {thirty_seconds_ago.isoformat()}...")
    
    with session_scope() as session:
        logs = session.query(FlowDetectionLog).filter(
            FlowDetectionLog.created_at >= thirty_seconds_ago
        ).order_by(FlowDetectionLog.created_at.desc()).all()
        
        if not logs:
            print("No detection logs found in the last 30 seconds.")
            return
        
        print(f"Found {len(logs)} detection logs.")
        for log in logs:
            print("-" * 50)
            print(f"Time: {log.created_at}")
            print(f"Flow ID: {log.flow_id}")
            print(f"Label: {log.label}")
            print(f"Decision Level: {log.decision_level}")
            print(f"Probability: {log.prob:.4f}")
            print(f"Anomaly Score: {log.anomaly_score:.4f}")
            
            if log.payload_snapshot:
                payload = json.loads(log.payload_snapshot)
                print("Flow Features:")
                # Print relevant features for SYN flood detection
                # Usually SYN flood has high pkt_rate and specific protocol/ports
                print(f"  Src IP: {payload.get('src_ip')}")
                print(f"  Dst IP: {payload.get('dst_ip')}")
                print(f"  Protocol: {payload.get('protocol')}")
                print(f"  Pkt Rate: {payload.get('pkt_rate')}")
                print(f"  Byte Rate: {payload.get('byte_rate')}")
                print(f"  Duration: {payload.get('duration')}")
                print(f"  Pkt Count: {payload.get('pkt_count')}")
            else:
                print("No payload snapshot available.")

if __name__ == "__main__":
    analyze_recent_detections()
