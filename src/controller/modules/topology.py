import logging
import networkx as nx
from ryu.lib import hub
from ryu.topology.api import get_switch, get_link
import time
import sys
import os

# Add parent directory to path to import node_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from node_config import HOSTS, SWITCHES

class NodeInfo:
    def __init__(self, node_id, node_type, **kwargs):
        self.id = node_id
        self.type = node_type # 'switch', 'plc', 'hmi', etc.
        self.name = kwargs.get('name', str(node_id))
        self.zone = kwargs.get('zone', 'Unknown') # Network Zone
        self.status = kwargs.get('status', 'online')
        self.ip = kwargs.get('ip')
        self.mac = kwargs.get('mac')
        self.dpid = kwargs.get('dpid') # For hosts, connected switch
        self.port = kwargs.get('port') # For hosts, connected port
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.metrics = {}

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'type': self.type,
            'zone': self.zone,
            'status': self.status,
            'ip': self.ip,
            'mac': self.mac,
            'dpid': str(self.dpid) if self.dpid else None,
            'port': self.port,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'metrics': self.metrics
        }

class TopologyManager:
    def __init__(self, app, notification_manager):
        self.app = app
        self.logger = logging.getLogger('TopologyManager')
        self.notification = notification_manager
        
        self.net = nx.Graph()
        self.nodes = {} # {id: NodeInfo}
        self.switches = [] # Keep for backward compatibility or easy iteration
        self.links = {} # {(src_dpid, src_port): (dst_dpid, dst_port)}
        
        # Deprecated but kept for compatibility until full refactor
        self.host_location = {} # {mac: (dpid, port)}
        self.host_ips = {} # {mac: ip}
        self.last_learned_time = {} # {mac: timestamp}
        
        # Cache for MST to avoid recalculation on every packet
        self._mst_cache = None
        self._mst_dirty = True

    def add_switch(self, dpid):
        """Manually add a switch to the topology"""
        if dpid not in self.switches:
            self.switches.append(dpid)
            
            # Lookup name from config
            dpid_str = "{:016x}".format(dpid)
            config = SWITCHES.get(dpid_str, {})
            if isinstance(config, str):
                name = config
                zone = 'Unknown'
            else:
                name = config.get('name', f"s{dpid}")
                zone = config.get('zone', 'Unknown')
            
            self.nodes[dpid] = NodeInfo(dpid, 'switch', name=name, zone=zone, status='online')
            self.net.add_node(dpid)
            self._mst_dirty = True
            self.logger.info("Switch %s (%s) added to topology", dpid, name)
            
            # Push network status update
            self.notification.push_network_status({
                'node_id': str(dpid),
                'status': 'online'
            })

    def remove_switch(self, dpid):
        """Manually remove a switch from the topology"""
        if dpid in self.switches:
            self.switches.remove(dpid)
            if dpid in self.nodes:
                del self.nodes[dpid]
            if self.net.has_node(dpid):
                self.net.remove_node(dpid)
            self._mst_dirty = True
            self.logger.info("Switch %s removed from topology", dpid)
            
            # Push network status update
            self.notification.push_network_status({
                'node_id': str(dpid),
                'status': 'offline'
            })
            
            # Cleanup hosts attached to this switch
            hosts_to_remove = []
            for mac, (host_dpid, port) in self.host_location.items():
                if host_dpid == dpid:
                    hosts_to_remove.append(mac)
            
            for mac in hosts_to_remove:
                self.unregister_host(mac)

    def start_discovery(self):
        # hub.spawn(self._discover_topology)
        pass

    def _discover_topology(self):
        """Periodically discover topology"""
        while True:
            hub.sleep(2)
            
            # Get switches
            switch_list = get_switch(self.app, None)
            current_switches = [switch.dp.id for switch in switch_list]
            
            # Update switches list and graph nodes
            for dpid in current_switches:
                if dpid not in self.switches:
                    self.switches.append(dpid)
                    
                    dpid_str = "{:016x}".format(dpid)
                    config = SWITCHES.get(dpid_str, {})
                    if isinstance(config, str):
                        name = config
                        zone = 'Unknown'
                    else:
                        name = config.get('name', f"s{dpid}")
                        zone = config.get('zone', 'Unknown')
                    
                    self.nodes[dpid] = NodeInfo(dpid, 'switch', name=name, zone=zone, status='online')
                    self.net.add_node(dpid)
                    self._mst_dirty = True
            
            # Handle removed switches (though usually handled by events)
            for dpid in list(self.switches):
                if dpid not in current_switches:
                    self.remove_switch(dpid)

            # Get links
            link_list = get_link(self.app, None)
            
            # Update links
            # Note: We trust events for real-time updates, but this reconciles state
            # For now, we just log if there's a mismatch or rely on events primarily.
            # Re-building the graph edges here ensures we don't miss anything.
            
            # Optimization: Don't rebuild entire graph, just update edges
            active_links = set()
            for link in link_list:
                src = link.src.dpid
                dst = link.dst.dpid
                src_port = link.src.port_no
                dst_port = link.dst.port_no
                
                link_key = (src, src_port)
                active_links.add(link_key)
                active_links.add((dst, dst_port))

                if not self.net.has_edge(src, dst):
                    self.net.add_edge(src, dst, weight=1, port={src: src_port, dst: dst_port})
                    self.links[link_key] = (dst, dst_port)
                    self.links[(dst, dst_port)] = (src, src_port)
                    self._mst_dirty = True

    def handle_link_add(self, link):
        src = link.src.dpid
        dst = link.dst.dpid
        src_port = link.src.port_no
        dst_port = link.dst.port_no
        
        self.links[(src, src_port)] = (dst, dst_port)
        self.links[(dst, dst_port)] = (src, src_port)
        
        if self.net.has_node(src) and self.net.has_node(dst):
            self.net.add_edge(src, dst, weight=1, port={src: src_port, dst: dst_port})
            self._mst_dirty = True
            # self.logger.info("Link added: %s:%s -> %s:%s", src, src_port, dst, dst_port)
            self.notification.push_topology_change('link_added', {
                'src': src, 'src_port': src_port,
                'dst': dst, 'dst_port': dst_port
            })

    def handle_link_delete(self, link):
        src = link.src.dpid
        dst = link.dst.dpid
        src_port = link.src.port_no
        dst_port = link.dst.port_no
        
        self.links.pop((src, src_port), None)
        self.links.pop((dst, dst_port), None)
        
        if self.net.has_edge(src, dst):
            self.net.remove_edge(src, dst)
            self._mst_dirty = True
            # self.logger.info("Link deleted: %s:%s -> %s:%s", src, src_port, dst, dst_port)
            self.notification.push_topology_change('link_removed', {
                'src': src, 'src_port': src_port,
                'dst': dst, 'dst_port': dst_port
            })

    def handle_switch_enter(self, dpid):
        if dpid not in self.switches:
            self.switches.append(dpid)
            
            dpid_str = "{:016x}".format(dpid)
            config = SWITCHES.get(dpid_str, {})
            if isinstance(config, str):
                name = config
                zone = 'Unknown'
            else:
                name = config.get('name', f"s{dpid}")
                zone = config.get('zone', 'Unknown')
            
            self.nodes[dpid] = NodeInfo(dpid, 'switch', name=name, zone=zone, status='online')
            self.net.add_node(dpid)
            self._mst_dirty = True
            self.notification.push_topology_change('switch_added', {
                'dpid': dpid,
                'type': 'switch',
                'name': name,
                'zone': zone
            })

    def handle_switch_leave(self, dpid):
        if dpid in self.switches:
            self.switches.remove(dpid)
            if dpid in self.nodes:
                del self.nodes[dpid]
            if self.net.has_node(dpid):
                self.net.remove_node(dpid)
            self._mst_dirty = True
            self.notification.push_topology_change('switch_removed', {'dpid': dpid})

    def get_mst(self):
        """Get Minimum Spanning Tree (Cached)"""
        if self._mst_dirty or self._mst_cache is None:
            if len(self.net.nodes) > 0:
                try:
                    self._mst_cache = nx.minimum_spanning_tree(self.net)
                    self._mst_dirty = False
                except Exception as e:
                    self.logger.error("MST calculation failed: %s", e)
                    return None
            else:
                return None
        return self._mst_cache

    def register_host(self, mac, dpid, port, ip=None):
        """Register or update host location"""
        if ip:
            self.host_ips[mac] = ip
            
        self.host_location[mac] = (dpid, port)
        
        # Lookup config
        config = HOSTS.get(mac, {})
        name = config.get('name', mac)
        node_type = config.get('type', 'node') # Default to 'node'
        zone = config.get('zone', 'Unknown')
        
        # Update NodeInfo
        if mac not in self.nodes:
            self.nodes[mac] = NodeInfo(mac, node_type, name=name, zone=zone, status='online', mac=mac, dpid=dpid, port=port, ip=ip)
        else:
            node = self.nodes[mac]
            node.dpid = dpid
            node.port = port
            if ip:
                node.ip = ip
            # Update type/name if it was default before (optional, but good if config loaded late)
            if node.type == 'node' and node_type != 'node':
                node.type = node_type
                node.name = name
                node.zone = zone
            
            node.last_seen = time.time()
        
        # Add host to graph for path finding
        if self.net.has_node(dpid):
            self.net.add_node(mac)
            self.net.add_edge(dpid, mac, port={dpid: port, mac: 0})
            self._mst_dirty = True # MST changes if we consider hosts part of it, but usually MST is switch-only. 
                                   # However, for shortest path, we need hosts in graph.
        
        self.notification.push_topology_change('host_added', {
            'mac': mac, 'dpid': dpid, 'port': port,
            'ip': self.host_ips.get(mac, ''),
            'type': node_type,
            'name': name,
            'zone': zone
        })

    def unregister_host(self, mac):
        """Unregister a host"""
        if mac in self.host_location:
            del self.host_location[mac]
            if mac in self.host_ips:
                del self.host_ips[mac]
            if mac in self.last_learned_time:
                del self.last_learned_time[mac]
            
            if mac in self.nodes:
                del self.nodes[mac]
            
            if self.net.has_node(mac):
                self.net.remove_node(mac)
                self._mst_dirty = True
            
            # self.logger.info("Host %s removed", mac)
            self.notification.push_topology_change('host_removed', {'mac': mac})

    def update_host_ip(self, mac, ip):
        """Update IP for a host"""
        self.host_ips[mac] = ip
        if mac in self.nodes:
            self.nodes[mac].ip = ip
            self.nodes[mac].last_seen = time.time()
        elif mac in self.host_location:
            # Should have been in nodes, but if not, create it?
            # Usually register_host creates it.
            pass
