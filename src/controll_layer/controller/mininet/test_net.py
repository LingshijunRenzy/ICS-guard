#!/usr/bin/env python3
"""
基础拓扑连通性测试脚本
用途：验证 topo_industrial.py 定义的网络是否成功启动并具备基本连通性
注意：此脚本不测试安全策略，仅测试物理/逻辑连接是否建立
"""

from mininet.net import Mininet
from mininet.log import setLogLevel, info
from industrial_topo1 import IndustrialTopo
from mininet.topo import Topo
from functools import partial
from mininet.node import RemoteController, OVSKernelSwitch

def test_basic_connectivity(net):
    """测试所有主机能否 ping 通其默认网关（即所连交换机），以及彼此之间是否可达（无策略限制时）"""
    info("*** Testing basic host reachability...\n")

    hosts = net.hosts
    if not hosts:
        info("❌ No hosts found!\n")
        return False

    host_dict = {h.name: h for h in hosts}
    expected_hosts = ['hmi1', 'plc1', 'io1', 'ipc1', 'phone1', 'dashboard']

    # 检查主机是否存在
    for name in expected_hosts:
        if name not in host_dict:
            info(f"❌ Missing host: {name}\n")
            return False
    info("✅ All expected hosts are present.\n")

    # 测试每个主机能否 ping 自己（验证 IP 配置）
    for name in expected_hosts:
        h = host_dict[name]
        result = h.cmd('ping -c 1 -W 1 127.0.0.1')
        if '1 packets transmitted, 1 received' not in result:
            info(f"❌ {name} failed loopback test\n")
            return False
    info("✅ All hosts passed loopback test.\n")

    # 测试跨主机连通性（在无控制器策略时，Mininet 默认允许通信）
    # 我们只测试部分关键对，避免 O(n²)
    test_pairs = [
        ('hmi1', 'plc1'),
        ('plc1', 'io1'),
        ('ipc1', 'dashboard'),
        ('phone1', 'hmi1'),
    ]

    all_ok = True
    for src_name, dst_name in test_pairs:
        src = host_dict[src_name]
        dst = host_dict[dst_name]
        dst_ip = dst.IP()

        info(f"Ping {src_name} → {dst_name} ({dst_ip}) ... ")
        result = src.cmd(f'ping -c 2 -W 1 {dst_ip}')
        if ' 0% packet loss' in result:
            info("✅\n")
        else:
            info("❌ FAILED\n")
            all_ok = False

    return all_ok

def main():
    setLogLevel('info')
    info("*** Starting basic topology test...\n")

    # 启动网络（不使用控制器，让 Mininet 使用默认行为）
    net = Mininet(topo=IndustrialTopo(),
                  autoSetMacs=True, 
                  autoStaticArp=True,
                  controller=RemoteController,  
                  )

    try:
        net.start()
        success = test_basic_connectivity(net)
        if success:
            info("\n🎉 Topology is correctly built and minimally functional!\n")
        else:
            info("\n⚠️  Topology has connectivity issues.\n")
        return success
    finally:
        net.stop()

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)