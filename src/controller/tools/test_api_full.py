import requests
import json
import time
import sys

BASE_URL = "http://localhost:8080"

def print_step(step_name):
    print("\n" + "="*50)
    print(f"Testing: {step_name}")
    print("="*50)

def get_token():
    print_step("Authentication")
    url = f"{BASE_URL}/auth/token"
    payload = {
        "client_id": "admin",
        "client_secret": "password"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            print(f"Token obtained successfully")
            return token
        else:
            print(f"Failed to get token: {response.text}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_policies(token):
    print_step("Policy Management")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create Policy
    print("\n[1] Create Policy")
    url = f"{BASE_URL}/policies"
    payload = {
        "policy": {
            "name": "Test Policy",
            "type": "flow",
            "action": "allow"
        }
    }
    policy_id = None
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code == 201:
            policy_id = response.json().get('policy_id')
    except Exception as e:
        print(f"Error: {e}")

    if not policy_id:
        print("Skipping remaining policy tests due to creation failure")
        return

    # 2. Get Policy
    print(f"\n[2] Get Policy {policy_id}")
    url = f"{BASE_URL}/policies/{policy_id}"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # 3. List Policies
    print("\n[3] List Policies")
    url = f"{BASE_URL}/policies"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # 4. Apply Policy
    print(f"\n[4] Apply Policy {policy_id}")
    url = f"{BASE_URL}/policies/{policy_id}/apply"
    try:
        response = requests.post(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # 5. Revoke Policy
    print(f"\n[5] Revoke Policy {policy_id}")
    url = f"{BASE_URL}/policies/{policy_id}/revoke"
    try:
        response = requests.post(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # 6. Delete Policy
    print(f"\n[6] Delete Policy {policy_id}")
    url = f"{BASE_URL}/policies/{policy_id}"
    try:
        response = requests.delete(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def test_stats(token):
    print_step("Statistics")
    headers = {"Authorization": f"Bearer {token}"}

    # Node Stats
    print("\n[1] Node Stats")
    url = f"{BASE_URL}/nodes/stats"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # Link Stats
    print("\n[2] Link Stats")
    url = f"{BASE_URL}/links/stats"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def test_alerts_logs(token):
    print_step("Alerts & Logs")
    headers = {"Authorization": f"Bearer {token}"}

    # Alerts
    print("\n[1] Alerts")
    url = f"{BASE_URL}/alerts"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # Honeypot Logs
    print("\n[2] Honeypot Logs")
    url = f"{BASE_URL}/honeypot/logs"
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    token = get_token()
    if not token:
        sys.exit(1)
    
    test_policies(token)
    test_stats(token)
    test_alerts_logs(token)

if __name__ == "__main__":
    main()
