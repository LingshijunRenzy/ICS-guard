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
            print(f"Full Response: {json.dumps(data, indent=2)}")
            return token
        else:
            print(f"Failed to get token: {response.text}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_topology(token):
    print_step("Get Topology")
    url = f"{BASE_URL}/topology"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            nodes = data.get('nodes', [])
            links = data.get('links', [])
            print(f"Nodes found: {len(nodes)}")
            print(f"Links found: {len(links)}")
            print(f"Full Response: {json.dumps(data, indent=2)}")
            return nodes, links
        else:
            print(f"Failed to get topology: {response.text}")
            return [], []
    except Exception as e:
        print(f"Error: {e}")
        return [], []

def check_node_status(token, nodes):
    print_step("Check Node Status")
    if not nodes:
        print("No nodes to check.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    # Check first 3 nodes
    for node in nodes[:3]:
        node_id = node.get('id')
        url = f"{BASE_URL}/nodes/{node_id}/status"
        try:
            response = requests.get(url, headers=headers)
            print(f"Node {node_id} Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error checking node {node_id}: {e}")

def check_link_status(token, links):
    print_step("Check Link Status")
    if not links:
        print("No links to check.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    # Check first 3 links
    for link in links[:3]:
        link_id = link.get('id')
        if not link_id:
            print("Link without ID found, skipping.")
            continue
            
        url = f"{BASE_URL}/links/{link_id}/status"
        try:
            response = requests.get(url, headers=headers)
            print(f"Link {link_id} Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error checking link {link_id}: {e}")

def control_node(token, nodes):
    print_step("Control Node (Restart)")
    if not nodes:
        print("No nodes to control.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    node = nodes[0]
    node_id = node.get('id')
    url = f"{BASE_URL}/nodes/{node_id}/restart"
    
    try:
        response = requests.post(url, headers=headers)
        print(f"Restart Node {node_id}: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error controlling node {node_id}: {e}")

def control_link(token, links):
    print_step("Control Link (Disable)")
    if not links:
        print("No links to control.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    link = links[0]
    link_id = link.get('id')
    if not link_id:
        return

    url = f"{BASE_URL}/links/{link_id}/disable"
    
    try:
        response = requests.post(url, headers=headers)
        print(f"Disable Link {link_id}: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error controlling link {link_id}: {e}")

def main():
    print("Starting API Test Script...")
    
    # 1. Get Token
    token = get_token()
    if not token:
        print("Aborting tests due to authentication failure.")
        sys.exit(1)
        
    # 2. Get Topology
    nodes, links = get_topology(token)
    
    # 3. Check Status
    check_node_status(token, nodes)
    check_link_status(token, links)
    
    # 4. Control Operations
    control_node(token, nodes)
    control_link(token, links)
    
    print("\nTests Completed.")

if __name__ == "__main__":
    main()
