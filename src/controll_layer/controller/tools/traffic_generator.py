#!/usr/bin/env python3
"""
工业控制网络流量生成器 (基于 Modbus/TCP)
用于模拟 PLC (Server) 和 HMI/SCADA (Client) 之间的正常通信流量。

依赖: pymodbus
安装: pip install pymodbus

使用方法:
1. 启动 Modbus Server (模拟 PLC):
   python3 traffic_generator.py server --port 5020

2. 启动 Modbus Client (模拟 HMI):
   python3 traffic_generator.py client --target <PLC_IP> --port 5020 --interval 2
"""

import argparse
import time
import logging
import sys
import random
from pymodbus.server import StartTcpServer
from pymodbus.client import ModbusTcpClient
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    # pymodbus 3.x renamed ModbusSlaveContext to ModbusDeviceContext
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext

# 配置日志
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

def run_server(port):
    """运行 Modbus TCP 服务器 (模拟 PLC)"""
    print(f"[*] 正在启动 Modbus Server (PLC) 监听端口 {port}...")
    
    # 初始化数据存储 (模拟寄存器)
    # Discrete Inputs, Coils, Input Registers, Holding Registers
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [17]*100), # 初始值
        ir=ModbusSequentialDataBlock(0, [0]*100))
    
    # pymodbus 3.x uses 'devices' instead of 'slaves'
    context = ModbusServerContext(devices=store, single=True)
    
    # 启动服务器 (阻塞模式)
    try:
        StartTcpServer(context=context, address=("0.0.0.0", port))
    except Exception as e:
        print(f"[!] Server error: {e}")

def run_client(target_ip, port, interval):
    """运行 Modbus TCP 客户端 (模拟 HMI/SCADA)"""
    print(f"[*] 正在启动 Modbus Client (HMI) 连接至 {target_ip}:{port}...")
    client = ModbusTcpClient(target_ip, port=port)
    
    try:
        if not client.connect():
            print(f"[!] 无法连接到 {target_ip}:{port}")
            return

        print(f"[+] 已连接。开始周期性数据采集 (间隔 {interval}s)...")
        
        while True:
            # 模拟正常业务：读取保持寄存器 (Holding Registers)
            # 例如读取传感器数据
            # pymodbus 3.x uses 'device_id' instead of 'slave', and 'count' is keyword-only
            rr = client.read_holding_registers(0, count=10, device_id=1)
            if rr.isError():
                print(f"[!] 读取错误: {rr}")
            else:
                print(f"[>] 读取寄存器 [0-9]: {rr.registers}")
            
            # 模拟偶尔的写入操作 (控制指令)
            if random.random() < 0.1: # 10% 概率写入
                val = random.randint(0, 100)
                print(f"[<] 发送控制指令: 写入寄存器 0 = {val}")
                client.write_register(0, val, device_id=1)
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[*] 停止客户端...")
    except Exception as e:
        print(f"[!] 发生错误: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Industrial Traffic Generator (Modbus/TCP)")
    subparsers = parser.add_subparsers(dest="mode", help="运行模式")
    
    # Server parser
    server_parser = subparsers.add_parser("server", help="运行 Modbus Server (模拟 PLC)")
    server_parser.add_argument("--port", type=int, default=5020, help="监听端口 (默认: 5020)")
    
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
