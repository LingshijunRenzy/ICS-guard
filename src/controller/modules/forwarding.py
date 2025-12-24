import logging
import time
import zlib
import networkx as nx
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, tcp, udp, icmp

class ForwardingEngine:
    def __init__(self, topology_manager, policy_manager):
        self.logger = logging.getLogger('ForwardingEngine')
        self.topology = topology_manager
        self.policy = policy_manager
        self.switch_ports = {} # {dpid: [port_no]}

    def update_switch_ports(self, dpid, ports):
        self.switch_ports[dpid] = ports

    def handle_packet_in(self, msg, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        dst = eth.dst
        src = eth.src

        # Ignore LLDP/Multicast
        if eth.ethertype == 35020 or dst.startswith('33:33:') or dst == '01:80:c2:00:00:0e':
            return

        # Learn IP
        if eth.ethertype == 2054: # ARP
            arp_pkt = pkt.get_protocol(arp.arp)
            self.topology.update_host_ip(src, arp_pkt.src_ip)
            self.topology.update_host_ip(dst, arp_pkt.dst_ip)
        elif eth.ethertype == 0x0800: # IPv4
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                self.topology.update_host_ip(src, ip_pkt.src)
                self.topology.update_host_ip(dst, ip_pkt.dst)

        # Host Learning
        link_key = (dpid, in_port)
        if link_key not in self.topology.links:
            # Not a switch-to-switch link, so it's a host
            current_time = time.time()
            is_new = src not in self.topology.host_location
            is_moved = not is_new and self.topology.host_location[src] != (dpid, in_port)
            
            should_update = False
            if is_new:
                should_update = True
            elif is_moved:
                last_time = self.topology.last_learned_time.get(src, 0)
                if current_time - last_time > 2.0: # Flapping protection
                    should_update = True
            
            if should_update:
                self.topology.last_learned_time[src] = current_time
                self.topology.register_host(src, dpid, in_port, self.topology.host_ips.get(src))

        # Policy Check
        # We need to check policy BEFORE flooding or forwarding
        # But for flooding (ARP/Broadcast), we might want to be careful not to block essential traffic unless explicitly denied
        
        # Extract L3/L4 info for Policy Check
        src_ip = self.topology.host_ips.get(src)
        dst_ip = self.topology.host_ips.get(dst)
        protocol = None
        dst_port = None
        
        if pkt:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                src_ip = ip_pkt.src
                dst_ip = ip_pkt.dst
                protocol = str(ip_pkt.proto)
                
                if ip_pkt.proto == 6: # TCP
                    tcp_pkt = pkt.get_protocol(tcp.tcp)
                    if tcp_pkt:
                        protocol = 'TCP'
                        dst_port = tcp_pkt.dst_port
                elif ip_pkt.proto == 17: # UDP
                    udp_pkt = pkt.get_protocol(udp.udp)
                    if udp_pkt:
                        protocol = 'UDP'
                        dst_port = udp_pkt.dst_port
                elif ip_pkt.proto == 1: # ICMP
                    protocol = 'ICMP'

        # Policy Check
        action, reason, action_params = self.policy.check_packet(dpid, src, dst, src_ip, dst_ip, protocol, dst_port)
        if action == 'drop' or action == 'isolate':
            self.logger.info("Packet %s by policy: %s -> %s (%s)", action, src, dst, reason)
            return

        # Forwarding Logic
        if dst == 'ff:ff:ff:ff:ff:ff' or dst not in self.topology.host_location:
            self._flood(datapath, msg, in_port, src, dst)
        else:
            self._shortest_path(datapath, msg, in_port, src, dst, pkt, action, action_params)

    def _flood(self, datapath, msg, in_port, src, dst):
        """Flood using MST"""
        dpid = datapath.id
        parser = datapath.ofproto_parser
        
        mst = self.topology.get_mst()
        actions = []
        
        ports = self.switch_ports.get(dpid, [])
        
        for port_no in ports:
            if port_no == in_port:
                continue
            
            link_key = (dpid, port_no)
            if link_key in self.topology.links:
                # Switch-to-switch link: Only forward if in MST
                dst_dpid, _ = self.topology.links[link_key]
                if mst and mst.has_edge(dpid, dst_dpid):
                    actions.append(parser.OFPActionOutput(port_no))
            else:
                # Host link: Always forward
                actions.append(parser.OFPActionOutput(port_no))
        
        if actions:
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions,
                                      data=msg.data)
            datapath.send_msg(out)

    def _shortest_path(self, datapath, msg, in_port, src, dst, pkt, policy_action='allow', policy_params=None):
        parser = datapath.ofproto_parser
        src_dpid = datapath.id
        
        if policy_action in ['log', 'inspect']:
             self.logger.info("Packet %s by policy: %s -> %s", policy_action, src, dst)
        
        # Handle Redirect (Change Destination)
        if policy_action == 'redirect' and policy_params:
            targets = policy_params.get('targets', [])
            # Support legacy format
            if not targets and 'redirect_target' in policy_params:
                 targets = [{'ip': policy_params['redirect_target']}]
                 
            if targets:
                target = targets[0] # Simple redirect to first target
                new_dst_ip = target.get('ip')
                if new_dst_ip:
                    # Find MAC for new IP
                    new_dst_mac = None
                    for mac, ip in self.topology.host_ips.items():
                        if ip == new_dst_ip:
                            new_dst_mac = mac
                            break
                    
                    if new_dst_mac:
                        self.logger.info("Redirecting packet %s -> %s to %s (%s)", src, dst, new_dst_ip, new_dst_mac)
                        dst = new_dst_mac
                        # Note: We will add SetField actions later

        if dst not in self.topology.host_location:
             self.logger.warning("Destination %s not found in topology, flooding", dst)
             self._flood(datapath, msg, in_port, src, dst)
             return

        dst_dpid, dst_port = self.topology.host_location[dst]
        
        try:
            path = nx.shortest_path(self.topology.net, src_dpid, dst_dpid)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.logger.warning("No path found from %s to %s, flooding", src_dpid, dst_dpid)
            self._flood(datapath, msg, in_port, src, dst)
            return

        if len(path) == 1:
            out_port = dst_port
        else:
            next_hop = path[1]
            edge_data = self.topology.net.get_edge_data(src_dpid, next_hop)
            out_port = edge_data['port'][src_dpid]

        actions = [parser.OFPActionOutput(out_port)]
        
        # Apply Redirect Actions (Set Field)
        if policy_action == 'redirect' and policy_params:
             # If we successfully changed 'dst' above, we should rewrite the packet headers
             # Check if we actually switched destination
             eth_pkt = pkt.get_protocol(ethernet.ethernet)
             if eth_pkt.dst != dst:
                 actions.insert(0, parser.OFPActionSetField(eth_dst=dst))
                 
                 # Also rewrite IP if IPv4
                 ip_pkt = pkt.get_protocol(ipv4.ipv4)
                 if ip_pkt:
                     # Find IP for the new dst MAC
                     new_ip = self.topology.host_ips.get(dst)
                     if new_ip:
                         actions.insert(0, parser.OFPActionSetField(ipv4_dst=new_ip))

        # Handle Rate Limiting (Throttle)
        meter_id = None
        if policy_action == 'throttle' and policy_params:
            try:
                # Generate unique meter ID based on flow signature (src, dst, dpid)
                # Meter ID must be > 0 and <= max_meter_id (usually 65535 or similar)
                flow_sig = f"{src}-{dst}-{datapath.id}"
                meter_id = (zlib.crc32(flow_sig.encode()) & 0xFFFF) + 1
                
                # Get rate limit params (kbps)
                # Default to 1000 kbps if not specified
                rate_kbps = int(policy_params.get('bandwidth_mbps', 1) * 1000)
                if rate_kbps <= 0: rate_kbps = 1000
                
                burst_size = int(policy_params.get('burst_size', 0))
                
                self.logger.info("Applying Rate Limit: %s kbps (Meter ID: %d) for %s -> %s", rate_kbps, meter_id, src, dst)
                self.add_meter(datapath, meter_id, rate_kbps, burst_size)
            except Exception as e:
                self.logger.error("Failed to apply rate limit: %s", e)
                meter_id = None

        # Build Match with L3/L4 info
        match_kwargs = {
            'in_port': in_port,
            'eth_dst': dst,
            'eth_src': src
        }

        if pkt:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                match_kwargs['eth_type'] = 0x0800
                match_kwargs['ipv4_src'] = ip_pkt.src
                match_kwargs['ipv4_dst'] = ip_pkt.dst
                match_kwargs['ip_proto'] = ip_pkt.proto
                
                if ip_pkt.proto == 6: # TCP
                    tcp_pkt = pkt.get_protocol(tcp.tcp)
                    if tcp_pkt:
                        match_kwargs['tcp_src'] = tcp_pkt.src_port
                        match_kwargs['tcp_dst'] = tcp_pkt.dst_port
                elif ip_pkt.proto == 17: # UDP
                    udp_pkt = pkt.get_protocol(udp.udp)
                    if udp_pkt:
                        match_kwargs['udp_src'] = udp_pkt.src_port
                        match_kwargs['udp_dst'] = udp_pkt.dst_port
                elif ip_pkt.proto == 1: # ICMP
                    icmp_pkt = pkt.get_protocol(icmp.icmp)
                    if icmp_pkt:
                        match_kwargs['icmpv4_type'] = icmp_pkt.type
                        match_kwargs['icmpv4_code'] = icmp_pkt.code

            elif pkt.get_protocol(arp.arp):
                match_kwargs['eth_type'] = 0x0806

        match = parser.OFPMatch(**match_kwargs)
        
        self.add_flow(datapath, 1, match, actions, idle_timeout=20, meter_id=meter_id)
        
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0, hard_timeout=0, meter_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if meter_id:
            inst.append(parser.OFPInstructionMeter(meter_id))
            
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        
        # Log flow installation for debugging
        if priority > 0: # Don't log table-miss flows
            # self.logger.info("Installing flow on dpid %s: match=%s", datapath.id, match)
            pass

        datapath.send_msg(mod)

    def add_meter(self, datapath, meter_id, rate, burst_size=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Band type: DROP
        bands = [parser.OFPMeterBandDrop(rate=rate, burst_size=burst_size)]
        
        req = parser.OFPMeterMod(datapath=datapath, command=ofproto.OFPMC_ADD,
                                 flags=ofproto.OFPMF_KBPS | ofproto.OFPMF_BURST,
                                 meter_id=meter_id, bands=bands)
        datapath.send_msg(req)

    def clear_flows(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        
        # Delete all flows
        mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE,
                                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                                match=match)
        datapath.send_msg(mod)
        
        # Re-install table-miss flow
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
