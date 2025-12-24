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
    else:
        parser.print_help()

    
    # Client parser
    client_parser = subparsers.add_parser("client", help="运行 Modbus Client (模拟 HMI)")
    client_parser.add_argument("--target", required=True, help="目标 PLC IP 地址")
    client_parser.add_argument("--port", type=int, default=5020, help="目标端口 (默认: 5020)")
    client_parser.add_argument("--interval", type=float, default=2.0, help="请求间隔秒数 (默认: 2.0)")
    
    args = parser.parse_args()
    
    if args.mode == "server":
        run_server(args.port)
    elif args.mode == "client":
        run_client(args.target, args.port, args.interval)
    else:
        parser.print_help()
