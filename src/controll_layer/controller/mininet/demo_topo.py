# mininet/demo_topo.py
from mininet.topo import Topo

class demoTopo(Topo):
    def build(self):
        
        # 核心层（双机）
        core1 = self.addSwitch('s0_1', dpid='0000000000000001')  # 核心1
        core2 = self.addSwitch('s0_2', dpid='0000000000000002')  # 核心2
        
        agg1 = self.addSwitch('s1_1', dpid='0000000000000011')  # 汇聚1
        agg2 = self.addSwitch('s1_2', dpid='0000000000000012')  # 汇聚2
        
        acc_hmi = self.addSwitch('s2_hmi', dpid='0000000000000021')  # HMI 接入
        acc_plc = self.addSwitch('s2_plc', dpid='0000000000000022')  # PLC 接入
        acc_io = self.addSwitch('s2_io', dpid='0000000000000023')   # IO 接入
        
        self.addHost('hmi1', ip='10.0.0.10/24')
        self.addHost('hmi2', ip='10.0.0.11/24')
                
        # 连接核心与汇聚
        self.addLink(core1, core2)  # 核心间链路
        self.addLink(core1, agg1)
        self.addLink(core2, agg2) 
        
        self.addLink(agg1, acc_hmi)
        self.addLink(agg1, acc_plc)
        self.addLink(agg2, acc_io)
        
        self.addLink(acc_hmi, 'hmi1')
        self.addLink(acc_hmi, 'hmi2')
        
topos = { 'demo' : (lambda: demoTopo()) }
        
    