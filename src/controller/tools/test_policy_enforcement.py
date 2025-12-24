import requests
import json
import time
import sys

# 尝试连接的端口列表
PORTS = [8080, 8000]
BASE_URL = None

def check_connection():
    global BASE_URL
    for port in PORTS:
        url = f"http://localhost:{port}/stats/switches" # Ryu 标准 API，无需认证即可测试连通性
        try:
            # 尝试连接，超时时间设置短一点
            requests.get(url, timeout=2)
            print(f"[+] 成功连接到控制器 (端口 {port})")
            BASE_URL = f"http://localhost:{port}"
            return True
        except requests.exceptions.ConnectionError:
            continue
        except Exception:
            # 如果是 404 等其他错误，说明端口是通的，只是路径不对，也算连接成功
            print(f"[+] 发现控制器 (端口 {port})")
            BASE_URL = f"http://localhost:{port}"
            return True
            
    return False

def get_token():
    if not BASE_URL:
        return None
        
    url = f"{BASE_URL}/auth/token"
    payload = {
        "client_id": "admin",
        "client_secret": "password"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"[-] 获取 Token 失败: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"[-] 获取 Token 异常: {e}")
        return None

def create_block_policy(token):
    url = f"{BASE_URL}/policies"
    headers = {"Authorization": f"Bearer {token}"}
    
    # 定义策略：禁止 HMI1 (10.0.0.10) -> PLC1 (10.0.1.10) 的 ICMP (Ping) 流量
    policy = {
        "policy": {
            "name": "Block HMI to PLC Ping",
            "priority": 100,
            "action": "deny",
            "status": "active",
            "conditions": {
                "src_ip": "10.0.0.10",
                "dst_ip": "10.0.1.10",
                "protocol": "ICMP" 
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=policy)
    if response.status_code == 200:
        policy_id = response.json().get('policy_id')
        print(f"\n[+] 策略已创建! ID: {policy_id}")
        print(f"    内容: 禁止 10.0.0.10 -> 10.0.1.10 的 ICMP 流量")
        return policy_id
    else:
        print(f"[-] 创建策略失败: {response.text}")
        return None

def delete_policy(token, policy_id):
    url = f"{BASE_URL}/policies/{policy_id}"
    headers = {"Authorization": f"Bearer {token}"}
    requests.delete(url, headers=headers)
    print(f"[-] 策略 {policy_id} 已删除。")

def main():
    print("--- 安全策略生效测试 ---")
    
    # 0. 检查连接
    if not check_connection():
        print("\n[!] 错误: 无法连接到 SDN 控制器。")
        print("请确保控制器已启动。运行命令:")
        print("  cd /home/nokk/Course/SDN/industrial_SDN/controll_layer/controller")
        print("  ryu-manager sdn_controller.py")
        return

    # 1. 获取 Token
    token = get_token()
    if not token:
        return

    # 2. 创建阻断策略
    policy_id = create_block_policy(token)
    if not policy_id:
        return

    print("\n>>> 请现在去 Mininet 终端执行: hmi1 ping -c 3 plc1")
    print(">>> 预期结果: Ping 应该失败 (100% packet loss)")
    
    input("\n按 Enter 键删除策略并恢复通信...")

    # 3. 删除策略
    delete_policy(token, policy_id)
    
    print("\n>>> 请再次去 Mininet 终端执行: hmi1 ping -c 3 plc1")
    print(">>> 预期结果: Ping 应该成功 (0% packet loss)")

if __name__ == "__main__":
    main()
