# mininet/topo_industrial.py
from mininet.topo import Topo

class IndustrialTopo(Topo):
    def build(self):
        # --- Core Layer (Redundant) ---
        core1 = self.addSwitch('s_core1', dpid='0000000000000001')
        core2 = self.addSwitch('s_core2', dpid='0000000000000002')

        # --- Aggregation Layer (Zones) ---
        agg_a = self.addSwitch('s_agg_a', dpid='0000000000000011') # Zone A: Manufacturing
        agg_b = self.addSwitch('s_agg_b', dpid='0000000000000012') # Zone B: Assembly
        agg_c = self.addSwitch('s_agg_c', dpid='0000000000000013') # Zone C: Control Room
        agg_d = self.addSwitch('s_agg_d', dpid='0000000000000014')    # DMZ

        # Core <-> Aggregation Links (Dual homing for redundancy)
        for agg in [agg_a, agg_b, agg_c, agg_d]:
            self.addLink(core1, agg)
            self.addLink(core2, agg)

        # Aggregation Horizontal Links (Ring-like or redundancy)
        self.addLink(agg_a, agg_b)
        self.addLink(agg_c, agg_d)

        # --- Access Layer ---
        acc_a1 = self.addSwitch('s_acc_a1', dpid='0000000000000021')
        acc_b1 = self.addSwitch('s_acc_b1', dpid='0000000000000022')
        acc_c1 = self.addSwitch('s_acc_c1', dpid='0000000000000023')
        acc_d1 = self.addSwitch('s_acc_d1', dpid='0000000000000024')

        self.addLink(agg_a, acc_a1)
        self.addLink(agg_b, acc_b1)
        self.addLink(agg_c, acc_c1)
        self.addLink(agg_d, acc_d1)

        # --- Hosts (Zone A) ---
        hmi1 = self.addHost('hmi1', ip='10.0.1.10/16', mac='00:00:00:00:00:01')
        plc1 = self.addHost('plc1', ip='10.0.1.20/16', mac='00:00:00:00:00:02')
        sensor1 = self.addHost('sensor1', ip='10.0.1.30/16', mac='00:00:00:00:00:03')
        self.addLink(hmi1, acc_a1)
        self.addLink(plc1, acc_a1)
        self.addLink(sensor1, acc_a1)

        # --- Hosts (Zone B) ---
        hmi2 = self.addHost('hmi2', ip='10.0.2.10/16', mac='00:00:00:00:00:04')
        plc2 = self.addHost('plc2', ip='10.0.2.20/16', mac='00:00:00:00:00:05')
        robot1 = self.addHost('robot1', ip='10.0.2.30/16', mac='00:00:00:00:00:06')
        self.addLink(hmi2, acc_b1)
        self.addLink(plc2, acc_b1)
        self.addLink(robot1, acc_b1)

        # --- Hosts (Zone C) ---
        scada = self.addHost('scada', ip='10.0.3.10/16', mac='00:00:00:00:00:07')
        ws1 = self.addHost('ws1', ip='10.0.3.20/16', mac='00:00:00:00:00:08')
        self.addLink(scada, acc_c1)
        self.addLink(ws1, acc_c1)

        # --- Hosts (DMZ) ---
        historian = self.addHost('historian', ip='10.0.4.10/16', mac='00:00:00:00:00:09')
        web_portal = self.addHost('web_portal', ip='10.0.4.20/16', mac='00:00:00:00:00:10')
        self.addLink(historian, acc_d1)
        self.addLink(web_portal, acc_d1)

topos = { 'topo' : (lambda: IndustrialTopo()) }