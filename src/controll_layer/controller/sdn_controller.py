from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication
from ryu.topology import switches
from ryu.lib import hub

# Import Modules

from modules.notification import NotificationManager
from modules.topology import TopologyManager
from modules.traffic import TrafficMonitor
from modules.policy import PolicyManager
from modules.forwarding import ForwardingEngine
from api import SDNControllerAPI, API_INSTANCE_NAME

class SDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'wsgi': WSGIApplication,
        'switches': switches.Switches
    }

    def __init__(self, *args, **kwargs):
        super(SDNController, self).__init__(*args, **kwargs)
        self.name = 'sdn_controller'
        
        # Initialize Modules
        self.notification = NotificationManager()
        self.topology = TopologyManager(self, self.notification)
        self.traffic = TrafficMonitor(self, self.notification, self.topology)
        self.policy = PolicyManager()
        self.forwarding = ForwardingEngine(self.topology, self.policy)
        
        # Register WSGI App
        wsgi = kwargs['wsgi']
        wsgi.register(SDNControllerAPI, {API_INSTANCE_NAME: self})
        
        # Start Background Tasks
        self.topology.start_discovery()
        self.traffic.start_monitoring()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        # Install Table-Miss Flow
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.forwarding.add_flow(datapath, 0, match, actions)
        
        # Request Port Description to get ports
        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        dpid = datapath.id
        ports = [p.port_no for p in ev.msg.body]
        self.forwarding.update_switch_ports(dpid, ports)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        self.traffic.handle_flow_stats_reply(ev.msg.datapath.id, ev.msg.body, self.topology.host_ips)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        self.traffic.handle_port_stats_reply(ev.msg.datapath.id, ev.msg.body)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        self.forwarding.handle_packet_in(ev.msg, ev.msg.datapath)

    def clear_all_flows(self):
        self.logger.info("Clearing all flows to enforce new policies")
        for datapath in self.traffic.datapaths.values():
            self.forwarding.clear_flows(datapath)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id:
                return
            self.traffic.register_datapath(datapath)
            self.topology.add_switch(datapath.id)
        elif ev.state == DEAD_DISPATCHER:
            if not datapath.id:
                return
            self.traffic.unregister_datapath(datapath.id)
            self.topology.remove_switch(datapath.id)

