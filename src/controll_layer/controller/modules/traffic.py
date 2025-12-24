import logging
import time
import datetime
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

class TrafficMonitor:
    def __init__(self, app, notification_manager, topology_manager):
        self.app = app
        self.logger = logging.getLogger('TrafficMonitor')
        self.notification = notification_manager
        self.topology = topology_manager
        
        self.datapaths = {}
        self.port_stats = {} # {dpid: {port_no: stats_dict}}
        self.flow_stats_history = {} # {flow_id: (packet_count, byte_count, timestamp)}
        self.active_flows = set() # {flow_id}
        self.active_flow_data = {} # {flow_id: flow_data_dict}
        self.last_pushed_stats = {} # {ui_flow_id: flow_data_dict}
        self.last_pushed_network_status = {} # {dpid: metrics}

    def register_datapath(self, datapath):
        self.datapaths[datapath.id] = datapath

    def unregister_datapath(self, dpid):
        if dpid in self.datapaths:
            del self.datapaths[dpid]
        if dpid in self.port_stats:
            del self.port_stats[dpid]

    def start_monitoring(self):
        hub.spawn(self._monitor_traffic)

    def _monitor_traffic(self):
        while True:
            hub.sleep(1)
            # self.logger.info("Requesting stats from %d switches...", len(self.datapaths))
            for datapath in self.datapaths.values():
                parser = datapath.ofproto_parser
                # Request Flow Stats
                req = parser.OFPFlowStatsRequest(datapath)
                datapath.send_msg(req)
                # Request Port Stats
                req_port = parser.OFPPortStatsRequest(datapath, 0, ofproto_v1_3.OFPP_ANY)
                datapath.send_msg(req_port)

    def handle_port_stats_reply(self, dpid, body):
        current_time = time.time()
        
        if dpid not in self.port_stats:
            self.port_stats[dpid] = {}
            
        for stat in body:
            port_no = stat.port_no
            if port_no == ofproto_v1_3.OFPP_LOCAL:
                continue
                
            prev_stats = self.port_stats[dpid].get(port_no)
            
            tx_bytes = stat.tx_bytes
            rx_bytes = stat.rx_bytes
            tx_errors = stat.tx_errors
            rx_errors = stat.rx_errors
            
            tx_bandwidth = 0.0
            rx_bandwidth = 0.0
            
            if prev_stats:
                prev_tx = prev_stats['tx_bytes']
                prev_rx = prev_stats['rx_bytes']
                prev_time = prev_stats['timestamp']
                
                delta_time = current_time - prev_time
                if delta_time > 0:
                    tx_bandwidth = (tx_bytes - prev_tx) * 8.0 / delta_time
                    rx_bandwidth = (rx_bytes - prev_rx) * 8.0 / delta_time
                    
            self.port_stats[dpid][port_no] = {
                'tx_bytes': tx_bytes,
                'rx_bytes': rx_bytes,
                'tx_errors': tx_errors,
                'rx_errors': rx_errors,
                'tx_bandwidth': tx_bandwidth,
                'rx_bandwidth': rx_bandwidth,
                'timestamp': current_time
            }

        # Calculate total throughput for the switch and push status
        total_throughput = 0.0
        for p_stat in self.port_stats[dpid].values():
            total_throughput += p_stat['tx_bandwidth'] + p_stat['rx_bandwidth']
            
        metrics = {
            'network_throughput': total_throughput,
            'cpu_usage': 0, 
            'memory_usage': 0 
        }
        
        # Update NodeInfo in TopologyManager
        node_data = None
        if dpid in self.topology.nodes:
            self.topology.nodes[dpid].metrics = metrics
            self.topology.nodes[dpid].last_seen = time.time()
            node_data = self.topology.nodes[dpid].to_dict()
            # Ensure status is present for compatibility if needed, or just rely on type
            node_data['status'] = 'online' 
        else:
            node_data = {
                'id': str(dpid),
                'type': 'switch',
                'metrics': metrics,
                'status': 'online'
            }
        
        if self._should_push_network_status(str(dpid), metrics):
            self.notification.push_network_status(node_data)
            self.last_pushed_network_status[str(dpid)] = metrics

    def _should_push_network_status(self, dpid, current_metrics):
        if dpid not in self.last_pushed_network_status:
            return True
            
        last_metrics = self.last_pushed_network_status[dpid]
        
        # Check throughput change > 10%
        curr_tp = current_metrics['network_throughput']
        last_tp = last_metrics['network_throughput']
        
        if last_tp == 0 and curr_tp > 0: return True
        if last_tp > 0 and curr_tp == 0: return True
        
        if last_tp > 0:
            change = abs(curr_tp - last_tp) / last_tp
            if change > 0.1: return True
            
        return False

    def handle_flow_stats_reply(self, dpid, body, host_ips):
        current_time = time.time()
        
        # Dictionary to aggregate flows by (dpid, src_mac, dst_mac) for UI display
        aggregated_stats = {} 
        
        for stat in body:
            if stat.priority == 0:
                continue
                
            match = stat.match
            if 'eth_src' not in match or 'eth_dst' not in match:
                continue
                
            src_mac = match['eth_src']
            dst_mac = match['eth_dst']

            if dst_mac == 'ff:ff:ff:ff:ff:ff' or dst_mac.startswith('01:80:c2') or dst_mac.startswith('33:33'):
                continue

            # Extract L3/L4 info for granular rate calculation
            ip_proto = match.get('ip_proto')
            tcp_src = match.get('tcp_src')
            tcp_dst = match.get('tcp_dst')
            udp_src = match.get('udp_src')
            udp_dst = match.get('udp_dst')
            ipv4_src = match.get('ipv4_src')
            ipv4_dst = match.get('ipv4_dst')
            
            src_port = tcp_src if tcp_src else udp_src
            dst_port = tcp_dst if tcp_dst else udp_dst
            protocol = 'TCP' if tcp_src else ('UDP' if udp_src else ('ICMP' if ip_proto == 1 else (str(ip_proto) if ip_proto else None)))
            
            # Granular ID for history tracking (Rate Calculation)
            granular_id = f"{dpid}-{src_mac}-{dst_mac}"
            if ipv4_src and ipv4_dst: granular_id += f"-{ipv4_src}-{ipv4_dst}"
            if protocol: granular_id += f"-{protocol}"
            if src_port: granular_id += f"-{src_port}"
            if dst_port: granular_id += f"-{dst_port}"

            # Calculate Rate for this granular flow
            pkt_rate = 0.0
            byte_rate = 0.0
            
            if granular_id in self.flow_stats_history:
                prev_pkt, prev_byte, prev_time = self.flow_stats_history[granular_id]
                delta_time = current_time - prev_time
                if delta_time > 0:
                    pkt_rate = (stat.packet_count - prev_pkt) / delta_time
                    byte_rate = (stat.byte_count - prev_byte) / delta_time
                    if pkt_rate < 0: pkt_rate = 0.0
                    if byte_rate < 0: byte_rate = 0.0
            
            self.flow_stats_history[granular_id] = (stat.packet_count, stat.byte_count, current_time)
            
            # Aggregate for UI (Key: dpid-src-dst)
            ui_flow_id = f"{dpid}-{src_mac}-{dst_mac}"
            
            if ui_flow_id not in aggregated_stats:
                duration = stat.duration_sec + stat.duration_nsec / 1e9
                now_dt = datetime.datetime.fromtimestamp(current_time)
                start_dt = datetime.datetime.fromtimestamp(current_time - duration)
                
                aggregated_stats[ui_flow_id] = {
                    'flow_id': ui_flow_id,
                    'dpid': str(dpid),
                    'src_mac': src_mac,
                    'dst_mac': dst_mac,
                    'src_ip': ipv4_src or host_ips.get(src_mac),
                    'dst_ip': ipv4_dst or host_ips.get(dst_mac),
                    'pkt_rate': 0.0,
                    'byte_rate': 0.0,
                    'packet_count': 0,
                    'byte_count': 0,
                    'protocol': protocol, # Keep last seen protocol or 'MIXED'
                    'timestamp': current_time,
                    'start_time': start_dt.isoformat(),
                    'end_time': now_dt.isoformat()
                }
            
            # Accumulate stats
            agg = aggregated_stats[ui_flow_id]
            agg['pkt_rate'] += pkt_rate
            agg['byte_rate'] += byte_rate
            agg['packet_count'] += stat.packet_count
            agg['byte_count'] += stat.byte_count
            # If multiple protocols exist, we might want to indicate that, but keeping simple for now

        # Process Aggregates for Notification
        seen_ui_flows = set(aggregated_stats.keys())
        
        for ui_flow_id, flow_data in aggregated_stats.items():
            # Only push update if aggregate flow is active
            is_active = flow_data['pkt_rate'] > 0 or flow_data['byte_rate'] > 0
            should_push = False
            
            if is_active:
                self.active_flows.add(ui_flow_id)
                self.active_flow_data[ui_flow_id] = flow_data
                
                # Check if we should push based on rate change
                if self._should_push_update(ui_flow_id, flow_data):
                    should_push = True
                    self.last_pushed_stats[ui_flow_id] = flow_data
                else:
                    should_push = False
            else:
                if ui_flow_id in self.active_flows:
                    self.active_flows.remove(ui_flow_id)
                    if ui_flow_id in self.active_flow_data:
                        del self.active_flow_data[ui_flow_id]
                    should_push = True # Push one last update with 0 rate to signal stop
                    # self.logger.info("Flow %s stopped (Rate: 0)", ui_flow_id)
                    # Remove from last pushed stats so next start is detected
                    if ui_flow_id in self.last_pushed_stats:
                        del self.last_pushed_stats[ui_flow_id]
                else:
                    should_push = False # Suppress redundant idle update
            
            if should_push:
                self.notification.push_flow_update(flow_data)

        # Check for flows that disappeared from this switch (Timeout)
        prefix = f"{dpid}-"
        disappeared_flows = [fid for fid in self.active_flows if fid.startswith(prefix) and fid not in seen_ui_flows]
        
        for fid in disappeared_flows:
            self.active_flows.remove(fid)
            # self.logger.info("Flow %s disappeared (Timeout)", fid)
            
            if fid in self.active_flow_data:
                stop_data = self.active_flow_data[fid].copy()
                stop_data['pkt_rate'] = 0.0
                stop_data['byte_rate'] = 0.0
                stop_data['timestamp'] = current_time
                self.notification.push_flow_update(stop_data)
                del self.active_flow_data[fid]
            
            if fid in self.last_pushed_stats:
                del self.last_pushed_stats[fid]
            
            # Note: We don't delete from flow_stats_history here because that uses granular IDs
            # We might need a separate cleanup for flow_stats_history if it grows too large, 
            # but for now we focus on UI correctness.

    def _should_push_update(self, flow_id, current_data):
        if flow_id not in self.last_pushed_stats:
            return True
            
        last_data = self.last_pushed_stats[flow_id]
        
        # Check for rate change > 10%
        current_rate = current_data['pkt_rate']
        last_rate = last_data['pkt_rate']
        
        if last_rate == 0 and current_rate > 0: return True
        if last_rate > 0 and current_rate == 0: return True
        
        if last_rate > 0:
            change = abs(current_rate - last_rate) / last_rate
            if change > 0.1: return True
            
        # Also check byte rate
        current_bytes = current_data['byte_rate']
        last_bytes = last_data['byte_rate']
        
        if last_bytes == 0 and current_bytes > 0: return True
        if last_bytes > 0 and current_bytes == 0: return True
        
        if last_bytes > 0:
            change = abs(current_bytes - last_bytes) / last_bytes
            if change > 0.1: return True
            
        return False
