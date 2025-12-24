from mininet.net import Mininet
from mininet.log import setLogLevel, info
from industrial_topo1 import IndustrialTopo
from mininet.topo import Topo
from functools import partial
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
import os
import time

def main():
    setLogLevel('info')
    ryu_ctrl = RemoteController('ryu_controller', ip='127.0.0.1', port=6653)
    info("正在创建网路拓扑\n")
    topo = IndustrialTopo()
    net = Mininet(topo=IndustrialTopo(), switch=OVSKernelSwitch,
                  controller=ryu_ctrl)
    net.start()
    
    # 自动执行 pingall 以触发控制器发现主机
    info("正在执行 Pingall 以发现主机...\n")
    net.pingAll()
    
    # --- 自动启动工控背景流量 ---
    info("正在启动背景工控流量 (PLC1 <-> HMI1)...\n")
    plc1 = net.get('plc1')
    hmi1 = net.get('hmi1')
    
    # 获取 tools/traffic_generator.py 的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    traffic_script = os.path.join(project_root, 'tools', 'traffic_generator.py')
    
    # 1. 启动 PLC Server (后台运行)
    info(f"[*] 启动 PLC Server on {plc1.name} ({plc1.IP()})...\n")
    # 输出重定向到 /tmp 下以便调试
    plc1.cmd(f'python3 {traffic_script} server --port 5020 > /tmp/plc1.log 2>&1 &')
    
    time.sleep(2) # 等待 Server 启动
    
    # 2. 启动 HMI Client (后台运行)
    info(f"[*] 启动 HMI Client on {hmi1.name} ({hmi1.IP()}) -> PLC...\n")
    hmi1.cmd(f'python3 {traffic_script} client --target {plc1.IP()} --port 5020 --interval 2 > /tmp/hmi1.log 2>&1 &')
    
    info("[*] 流量生成已在后台启动。日志位于 /tmp/plc1.log 和 /tmp/hmi1.log\n")
    # -------------------------

    CLI(net)
    net.stop()

if __name__ == '__main__':
    main()
