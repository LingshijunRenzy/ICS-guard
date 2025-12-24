# mininet/topo_industrial.py
from mininet.topo import Topo

class IndustrialTopo(Topo):
    def build(self):
        # 核心层（双机）
        core1 = self.addSwitch('s0_1', dpid='0000000000000001')  # 核心1
        core2 = self.addSwitch('s0_2', dpid='0000000000000002')  # 核心2

        # 汇聚层（4台）
        agg1 = self.addSwitch('s1_1', dpid='0000000000000011')  # 汇聚1
        agg2 = self.addSwitch('s1_2', dpid='0000000000000012')  # 汇聚2
        agg3 = self.addSwitch('s1_3', dpid='0000000000000013')  # 汇聚3
        agg4 = self.addSwitch('s1_4', dpid='0000000000000014')  # 汇聚4

        # 接入层（按功能划分）
        acc_hmi = self.addSwitch('s2_hmi', dpid='0000000000000021')  # HMI 接入
        acc_plc = self.addSwitch('s2_plc', dpid='0000000000000022')  # PLC 接入
        acc_io = self.addSwitch('s2_io', dpid='0000000000000023')   # IO 接入
        acc_ipc1 = self.addSwitch('s2_ipc1', dpid='0000000000000024')  # IPC 接入1
        acc_phone = self.addSwitch('s2_phone', dpid='0000000000000025')  # Phone 接入
        acc_dashboard = self.addSwitch('s2_dash', dpid='0000000000000026')  # Dashboard 接入

        # 连接核心与汇聚
        self.addLink(core1, agg1)
        self.addLink(core1, agg2)
        self.addLink(core1, agg3)
        self.addLink(core1, agg4)
        self.addLink(core2, agg1)
        self.addLink(core2, agg2)
        self.addLink(core2, agg3)
        self.addLink(core2, agg4)

        # 汇聚层横向链路（仅汇聚1 ↔ 汇聚2）
        self.addLink(agg1, agg2)

        # 汇聚与接入连接（树状结构，无环）
        self.addLink(agg1, acc_hmi)
        self.addLink(agg1, acc_plc)
        self.addLink(agg2, acc_io)
        self.addLink(agg2, acc_ipc1)
        self.addLink(agg3, acc_phone)
        self.addLink(agg4, acc_dashboard)

        # 终端设备
        hmi1 = self.addHost('hmi1', ip='10.0.0.10/16', mac='00:00:00:00:00:01')
        plc1 = self.addHost('plc1', ip='10.0.1.10/16', mac='00:00:00:00:00:02')
        io1 = self.addHost('io1', ip='10.0.2.10/16', mac='00:00:00:00:00:03')
        ipc1 = self.addHost('ipc1', ip='10.0.3.10/16', mac='00:00:00:00:00:04')
        phone1 = self.addHost('phone1', ip='10.0.4.10/16', mac='00:00:00:00:00:05')
        dashboard = self.addHost('dashboard', ip='10.0.5.10/16', mac='00:00:00:00:00:06')

        # 连接终端到接入交换机
        self.addLink(hmi1, acc_hmi)
        self.addLink(plc1, acc_plc)
        self.addLink(io1, acc_io)
        self.addLink(ipc1, acc_ipc1)
        self.addLink(phone1, acc_phone)
        self.addLink(dashboard, acc_dashboard)

topos = { 'topo' : (lambda: IndustrialTopo()) }