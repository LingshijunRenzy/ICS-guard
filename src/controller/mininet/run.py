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
    info("正在启动背景工控流量...\n")
    
    # 获取主机对象
    hmi1 = net.get('hmi1')
    plc1 = net.get('plc1')
    sensor1 = net.get('sensor1')
    
    hmi2 = net.get('hmi2')
    plc2 = net.get('plc2')
    robot1 = net.get('robot1')
    
    scada = net.get('scada')
    ws1 = net.get('ws1')
    
    web_portal = net.get('web_portal')
    
    # 获取 tools/traffic_generator.py 的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    traffic_script = os.path.join(project_root, 'tools', 'traffic_generator.py')
    
    # 1. Zone A: PLC1 <-> HMI1 (Modbus)
    info(f"[*] [Zone A] Starting Modbus: PLC1 ({plc1.IP()}) <-> HMI1 ({hmi1.IP()})...\n")
    plc1.cmd(f'python3 {traffic_script} modbus-server --port 5020 > /tmp/plc1.log 2>&1 &')
    time.sleep(1)
    hmi1.cmd(f'python3 {traffic_script} modbus-client --target {plc1.IP()} --port 5020 --interval 2 > /tmp/hmi1.log 2>&1 &')

    # 2. Zone B: PLC2 <-> HMI2 (Modbus)
    info(f"[*] [Zone B] Starting Modbus: PLC2 ({plc2.IP()}) <-> HMI2 ({hmi2.IP()})...\n")
    plc2.cmd(f'python3 {traffic_script} modbus-server --port 5020 > /tmp/plc2.log 2>&1 &')
    time.sleep(1)
    hmi2.cmd(f'python3 {traffic_script} modbus-client --target {plc2.IP()} --port 5020 --interval 3 > /tmp/hmi2.log 2>&1 &')

    # 3. Zone C: SCADA Server (UDP Receiver)
    info(f"[*] [Zone C] Starting SCADA UDP Server on {scada.IP()}...\n")
    scada.cmd(f'python3 {traffic_script} udp-server --port 9000 > /tmp/scada.log 2>&1 &')

    # 4. Sensors/Robots -> SCADA (UDP Telemetry)
    info(f"[*] [Telemetry] Sensor1 & Robot1 -> SCADA...\n")
    sensor1.cmd(f'python3 {traffic_script} udp-sensor --target {scada.IP()} --port 9000 --interval 1 > /tmp/sensor1.log 2>&1 &')
    robot1.cmd(f'python3 {traffic_script} udp-sensor --target {scada.IP()} --port 9000 --interval 0.5 > /tmp/robot1.log 2>&1 &')

    # 5. DMZ: Web Portal (HTTP Server) <-> Workstation (HTTP Client)
    info(f"[*] [DMZ] Starting Web Portal on {web_portal.IP()}...\n")
    web_portal.cmd(f'python3 {traffic_script} http-server --port 80 > /tmp/web.log 2>&1 &')
    time.sleep(1)
    info(f"[*] [Office] Workstation -> Web Portal...\n")
    ws1.cmd(f'python3 {traffic_script} http-client --target {web_portal.IP()} --port 80 --interval 5 > /tmp/workstation.log 2>&1 &')
    
    info("[*] 所有流量生成已在后台启动。日志位于 /tmp/*.log\n")

    CLI(net)
    net.stop()

if __name__ == '__main__':
    main()
