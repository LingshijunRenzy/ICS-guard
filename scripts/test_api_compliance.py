#!/usr/bin/env python3
"""
测试应用层 API 是否符合 API 文档规范。
"""

import json
import sys
import requests

BASE_URL = "http://localhost:5000"
LOG_PATH = "/home/lingshi/coding/ICS-guard/.cursor/debug.log"


def log_result(hypothesis_id: str, location: str, message: str, data: dict):
    """记录测试结果到调试日志。"""
    import time
    entry = {
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": time.time(),
        "sessionId": "debug-session",
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def test_topology():
    """测试拓扑 API。"""
    resp = requests.get(f"{BASE_URL}/api/topology")
    data = resp.json()
    
    # 检查 Link 是否有 id 字段
    links = data.get("links", [])
    has_id = all("id" in link for link in links) if links else False
    
    log_result(
        "A",
        "test_api_compliance.py:test_topology",
        "Topology API Link id field check",
        {
            "links_count": len(links),
            "has_id_field": has_id,
            "links_sample": links[:2] if links else [],
        },
    )
    
    print(f"✓ Topology: {len(links)} links, has_id={has_id}")
    return has_id


def test_alerts():
    """测试告警 API。"""
    resp = requests.get(f"{BASE_URL}/api/alerts")
    data = resp.json()
    
    alerts = data.get("alerts", [])
    valid_severities = ["low", "medium", "high"]
    severities = [a.get("severity") for a in alerts]
    all_valid = all(s in valid_severities for s in severities)
    
    log_result(
        "C",
        "test_api_compliance.py:test_alerts",
        "Alerts severity validation",
        {
            "alerts_count": len(alerts),
            "severities": severities,
            "all_valid": all_valid,
        },
    )
    
    print(f"✓ Alerts: {len(alerts)} alerts, valid_severities={all_valid}")
    return all_valid


def test_policies():
    """测试策略 API。"""
    resp = requests.get(f"{BASE_URL}/api/policies")
    data = resp.json()
    
    policies = data.get("policies", [])
    valid_types = ["node", "connection", "flow"]
    types = [p.get("type") for p in policies]
    all_valid = all(t in valid_types for t in types)
    
    log_result(
        "D",
        "test_api_compliance.py:test_policies",
        "Policies type validation",
        {
            "policies_count": len(policies),
            "types": types,
            "all_valid": all_valid,
        },
    )
    
    print(f"✓ Policies: {len(policies)} policies, valid_types={all_valid}")
    return all_valid


def test_node_stats():
    """测试节点统计 API 响应结构。"""
    resp = requests.get(f"{BASE_URL}/api/nodes/stats")
    data = resp.json()
    
    # API 文档要求返回 {"stats": [...]}
    has_stats_key = "stats" in data
    stats = data.get("stats", [])
    
    log_result(
        "E",
        "test_api_compliance.py:test_node_stats",
        "Node stats response structure",
        {
            "has_stats_key": has_stats_key,
            "stats_count": len(stats),
            "response_keys": list(data.keys()),
        },
    )
    
    print(f"✓ Node Stats: has_stats_key={has_stats_key}, count={len(stats)}")
    return has_stats_key


def test_link_stats():
    """测试连接统计 API 响应结构。"""
    resp = requests.get(f"{BASE_URL}/api/links/stats")
    data = resp.json()
    
    # API 文档要求返回 {"stats": [...]}
    has_stats_key = "stats" in data
    stats = data.get("stats", [])
    
    log_result(
        "F",
        "test_api_compliance.py:test_link_stats",
        "Link stats response structure",
        {
            "has_stats_key": has_stats_key,
            "stats_count": len(stats),
            "response_keys": list(data.keys()),
        },
    )
    
    print(f"✓ Link Stats: has_stats_key={has_stats_key}, count={len(stats)}")
    return has_stats_key


def test_honeypot_logs():
    """测试蜜罐日志 API 响应结构。"""
    resp = requests.get(f"{BASE_URL}/api/honeypot/logs")
    data = resp.json()
    
    # API 文档要求返回 {"logs": [...]}
    has_logs_key = "logs" in data
    logs = data.get("logs", [])
    
    log_result(
        "G",
        "test_api_compliance.py:test_honeypot_logs",
        "Honeypot logs response structure",
        {
            "has_logs_key": has_logs_key,
            "logs_count": len(logs),
            "response_keys": list(data.keys()),
        },
    )
    
    print(f"✓ Honeypot Logs: has_logs_key={has_logs_key}, count={len(logs)}")
    return has_logs_key


def main():
    """运行所有测试。"""
    print("=" * 60)
    print("API Compliance Test")
    print("=" * 60)
    
    results = {
        "topology_link_id": test_topology(),
        "alerts_severity": test_alerts(),
        "policies_type": test_policies(),
        "node_stats_structure": test_node_stats(),
        "link_stats_structure": test_link_stats(),
        "honeypot_logs_structure": test_honeypot_logs(),
    }
    
    print("=" * 60)
    print("Summary:")
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n❌ {len(failed)} test(s) failed: {failed}")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

