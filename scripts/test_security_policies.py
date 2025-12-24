#!/usr/bin/env python3
"""
Security Policy Testing Script for ICS-guard
Tests the creation and enforcement configuration of various security policies.

Usage:
    python3 test_security_policies.py [command]

Commands:
    all         Run all policy tests (create & delete)
    isolate     Test Host Isolation Policy
    modbus      Test Modbus Protocol Blocking
    whitelist   Test IP Whitelist Policy
    throttle    Test Traffic Throttling Policy
    list        List all active policies
    clear       Delete all policies created by this script
"""

import requests
import json
import time
import sys
import argparse

# Configuration
CONTROLLER_PORTS = [8080, 8000]
BASE_URL = None
TOKEN = None

# Test Data
TARGET_HMI_MAC = "00:00:00:00:00:01"
TARGET_PLC_MAC = "00:00:00:00:00:02"

def find_controller():
    global BASE_URL
    print("[*] Searching for SDN Controller...")
    for port in CONTROLLER_PORTS:
        url = f"http://localhost:{port}/stats/switches"
        try:
            requests.get(url, timeout=2)
            print(f"[+] Found controller at http://localhost:{port}")
            BASE_URL = f"http://localhost:{port}"
            return True
        except requests.exceptions.ConnectionError:
            continue
        except Exception:
            # If we get a response (even 404), the server is there
            print(f"[+] Found controller at http://localhost:{port}")
            BASE_URL = f"http://localhost:{port}"
            return True
    print("[-] Controller not found. Please ensure Ryu controller is running.")
    return False

def authenticate():
    global TOKEN
    if not BASE_URL: return False
    
    url = f"{BASE_URL}/auth/token"
    # Default credentials as per existing tests
    payload = {
        "client_id": "admin",
        "client_secret": "password"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            TOKEN = response.json().get('access_token')
            print("[+] Authentication successful.")
            return True
        else:
            print(f"[-] Authentication failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"[-] Authentication error: {e}")
        return False

def create_policy(name, policy_def):
    if not TOKEN: return None
    
    url = f"{BASE_URL}/policies"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    payload = {
        "policy": policy_def
    }
    # Add name to the policy definition itself if not present, for the API wrapper
    if 'name' not in payload['policy']:
        payload['policy']['name'] = name

    print(f"\n[*] Creating Policy: {name}")
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            data = response.json()
            policy_id = data.get('policy_id') or data.get('id')
            print(f"[+] Success! Policy ID: {policy_id}")
            return policy_id
        else:
            print(f"[-] Failed: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"[-] Error creating policy: {e}")
        return None

def delete_policy(policy_id):
    if not TOKEN or not policy_id: return
    
    url = f"{BASE_URL}/policies/{policy_id}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    print(f"[*] Deleting Policy: {policy_id}")
    try:
        requests.delete(url, headers=headers)
        print(f"[+] Policy deleted.")
    except Exception as e:
        print(f"[-] Error deleting policy: {e}")

def list_policies():
    if not TOKEN: return
    
    url = f"{BASE_URL}/policies"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            policies = data.get('policies', [])
            print(f"\n--- Active Policies ({len(policies)}) ---")
            for p in policies:
                print(f"ID: {p.get('id')}")
                print(f"  Name: {p.get('name')}")
                print(f"  Action: {p.get('action')}")
                print(f"  Target: {p.get('target_id') or p.get('scope', {}).get('target_id')}")
                print(f"  Conditions: {p.get('conditions')}")
                print("-" * 30)
        else:
            print(f"[-] Failed to list policies: {response.status_code}")
    except Exception as e:
        print(f"[-] Error listing policies: {e}")

# --- Test Cases ---

def test_isolation():
    print("\n=== Test Case: Host Isolation ===")
    print(f"Target: {TARGET_HMI_MAC} (HMI1)")
    print("Goal: Block ALL traffic to/from this host.")
    
    policy = {
        "name": "TEST_Isolation_HMI1",
        "priority": 100,
        "action": "block",
        "status": "active",
        "scope": {
            "target_id": TARGET_HMI_MAC,
            "target_type": "device"
        },
        "conditions": {
            "denied_ips": ["*.*.*.*"]
        }
    }
    
    pid = create_policy("Isolation Test", policy)
    return pid

def test_modbus_block():
    print("\n=== Test Case: Modbus Protocol Blocking ===")
    print(f"Target: {TARGET_PLC_MAC} (PLC1)")
    print("Goal: Block TCP Port 502 (Modbus) traffic.")
    
    policy = {
        "name": "TEST_Block_Modbus",
        "priority": 90,
        "action": "block",
        "status": "active",
        "scope": {
            "target_id": TARGET_PLC_MAC,
            "target_type": "device"
        },
        "conditions": {
            "protocol": "tcp",
            "dst_port": 502
        }
    }
    
    pid = create_policy("Modbus Block Test", policy)
    return pid

def test_whitelist():
    print("\n=== Test Case: IP Whitelist ===")
    print(f"Target: {TARGET_HMI_MAC}")
    print("Goal: Only allow traffic from 10.0.0.5, block others.")
    
    policy = {
        "name": "TEST_Whitelist_Admin",
        "priority": 95,
        "action": "block", # The base action is block if not in whitelist
        "status": "active",
        "scope": {
            "target_id": TARGET_HMI_MAC,
            "target_type": "device"
        },
        "conditions": {
            "allowed_ips": ["10.0.0.5"]
        }
    }
    
    pid = create_policy("Whitelist Test", policy)
    return pid

def test_throttle():
    print("\n=== Test Case: Traffic Throttling ===")
    print(f"Target: {TARGET_HMI_MAC}")
    print("Goal: Limit bandwidth to 1Mbps.")
    
    policy = {
        "name": "TEST_Throttle_HMI",
        "priority": 80,
        "action": "throttle",
        "status": "active",
        "scope": {
            "target_id": TARGET_HMI_MAC,
            "target_type": "device"
        },
        "actions": {
            "primary_action": {
                "action_type": "throttle",
                "action_params": {
                    "rate_limit": {
                        "rate": "1000kbps",
                        "burst": "100kb"
                    }
                }
            }
        }
    }
    
    pid = create_policy("Throttle Test", policy)
    return pid

def run_all():
    pids = []
    pids.append(test_isolation())
    pids.append(test_modbus_block())
    pids.append(test_whitelist())
    pids.append(test_throttle())
    
    print("\n[!] All test policies created.")
    print("You can now verify enforcement using traffic_generator.py or Mininet CLI.")
    input("Press Enter to clean up and delete these policies...")
    
    for pid in pids:
        if pid: delete_policy(pid)

def main():
    parser = argparse.ArgumentParser(description="ICS-guard Policy Test Script")
    parser.add_argument('command', choices=['all', 'isolate', 'modbus', 'whitelist', 'throttle', 'list', 'clear'], 
                        help='Command to execute')
    args = parser.parse_args()

    if not find_controller():
        return

    if not authenticate():
        return

    if args.command == 'list':
        list_policies()
    elif args.command == 'all':
        run_all()
    elif args.command == 'isolate':
        pid = test_isolation()
        if pid: print(f"Policy {pid} created. Use 'python3 test_security_policies.py list' to view or delete manually via API.")
    elif args.command == 'modbus':
        pid = test_modbus_block()
        if pid: print(f"Policy {pid} created.")
    elif args.command == 'whitelist':
        pid = test_whitelist()
        if pid: print(f"Policy {pid} created.")
    elif args.command == 'throttle':
        pid = test_throttle()
        if pid: print(f"Policy {pid} created.")
    elif args.command == 'clear':
        # This is a bit risky without tracking IDs, so we'll just list them and ask user to delete manually or implement a "delete all test policies" if we can identify them by name
        print("To clear policies, please use the API or restart the controller (if in-memory).")
        list_policies()

if __name__ == "__main__":
    main()
