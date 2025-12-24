from ryu.app.wsgi import ControllerBase, route, websocket
from ryu.lib import hub
from webob import Response
import json
import jwt
import datetime
import time
try:
    from node_config import SWITCHES, HOSTS
except ImportError:
    SWITCHES = {}
    HOSTS = {}

API_INSTANCE_NAME = 'sdn_controller_api_app'

class SDNControllerAPI(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(SDNControllerAPI, self).__init__(req, link, data, **config)
        self.sdn_controller = data[API_INSTANCE_NAME]
        self.secret_key = "ics_guard_secret"

    def _json_response(self, data, status=200):
        body = json.dumps(data)
        return Response(content_type='application/json', body=body, status=status, charset='utf-8')

    @route('auth', '/auth/token', methods=['POST'])
    def auth_token(self, req, **kwargs):
        try:
            body = req.json if req.body else {}
        except ValueError:
            return self._json_response({'code': '400', 'message': 'Invalid JSON'}, status=400)
            
        client_id = body.get('client_id')
        client_secret = body.get('client_secret')
        
        # Simple mock authentication
        # In a real app, validate against a user database
        if (client_id == 'admin' and client_secret == 'password') or \
           (client_id == 'app-layer-client' and client_secret == 'app-layer-secret'):
            token_payload = {
                'client_id': client_id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            }
            token = jwt.encode(token_payload, self.secret_key, algorithm='HS256')
            
            return self._json_response({
                'access_token': token,
                'token_type': 'Bearer',
                'expires_in': 3600,
                'refresh_token': 'mock_refresh_token'
            })
        else:
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

    @route('auth_refresh', '/auth/refresh', methods=['GET'])
    def auth_refresh(self, req, **kwargs):
        auth_header = req.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
             return self._json_response({'code': '401', 'message': 'Missing or invalid token'}, status=401)
        
        # In a real app, we would verify the refresh token. 
        # Here we just issue a new access token if the header is present.
        token_payload = {
            'client_id': 'admin',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        new_token = jwt.encode(token_payload, self.secret_key, algorithm='HS256')
        
        return self._json_response({
            'access_token': new_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'refresh_token': 'mock_refresh_token_new'
        })

    @route('auth_verify', '/auth/verify', methods=['POST'])
    def auth_verify(self, req, **kwargs):
        try:
            body = req.json if req.body else {}
            token = body.get('token')
        except ValueError:
            return self._json_response({'code': '400', 'message': 'Invalid JSON'}, status=400)

        if not token:
             return self._json_response({'code': '400', 'message': 'Missing token'}, status=400)

        try:
            jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return self._json_response({'valid': True})
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return self._json_response({'valid': False})

    @route('auth_revoke', '/auth/revoke', methods=['POST'])
    def auth_revoke(self, req, **kwargs):
        # Mock revocation
        return self._json_response({'revoked': True})

    @route('topology', '/topology', methods=['GET'])
    def get_topology(self, req, **kwargs):
        # Verify token
        auth_header = req.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
             return self._json_response({'code': '401', 'message': 'Missing or invalid token'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return self._json_response({'code': '401', 'message': 'Token expired'}, status=401)
        except jwt.InvalidTokenError:
            return self._json_response({'code': '401', 'message': 'Invalid token'}, status=401)

        nodes = []
        links = []
        
        # Switches
        for dpid in self.sdn_controller.topology.switches:
            dpid_hex = "{:016x}".format(dpid)
            name = SWITCHES.get(dpid_hex, 'Switch{}'.format(dpid))
            nodes.append({
                'id': str(dpid),
                'name': name,
                'type': 'switch',
                'ip': '', 
                'status': 'online'
            })
            
        # Hosts
        for mac, (dpid, port) in self.sdn_controller.topology.host_location.items():
            host_info = HOSTS.get(mac, {})
            name = host_info.get('name', 'Host-{}'.format(mac))
            nodes.append({
                'id': mac,
                'name': name,
                'type': 'host',
                'ip': self.sdn_controller.topology.host_ips.get(mac, ''), 
                'status': 'online'
            })
            # Link between host and switch
            links.append({
                'id': '{}-{}'.format(dpid, mac),
                'source': str(dpid),
                'target': mac,
                'bandwidth': 100, 
                'status': 'active'
            })

        # Switch Links
        added_links = set()
        for (src_dpid, src_port), (dst_dpid, dst_port) in self.sdn_controller.topology.links.items():
            link_id_tuple = tuple(sorted((src_dpid, dst_dpid)))
            if link_id_tuple not in added_links:
                links.append({
                    'id': '{}-{}'.format(link_id_tuple[0], link_id_tuple[1]),
                    'source': str(src_dpid),
                    'target': str(dst_dpid),
                    'bandwidth': 1000, 
                    'status': 'active'
                })
                added_links.add(link_id_tuple)

        return self._json_response({
            'nodes': nodes,
            'links': links
        })

    def _verify_token(self, req):
        auth_header = req.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
             return False
        token = auth_header.split(' ')[1]
        try:
            jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return True
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return False

    @route('node_status', '/nodes/{node_id}/status', methods=['GET'])
    def get_node_status(self, req, node_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        # Check if node exists
        is_switch = False
        try:
            dpid = int(node_id)
            if dpid in self.sdn_controller.topology.switches:
                is_switch = True
        except ValueError:
            pass
            
        is_host = node_id in self.sdn_controller.topology.host_location
        
        if not is_switch and not is_host:
             return self._json_response({'code': '404', 'message': 'Node not found'}, status=404)

        return self._json_response({
            'node_id': node_id,
            'status': 'online',
            'last_updated': datetime.datetime.utcnow().isoformat(),
            'metrics': {
                'cpu_usage': 0,
                'memory_usage': 0,
                'network_throughput': 0
            }
        })

    @route('link_status', '/links/{link_id}/status', methods=['GET'])
    def get_link_status(self, req, link_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        
        return self._json_response({
            'link_id': link_id,
            'status': 'active',
            'last_updated': datetime.datetime.utcnow().isoformat(),
            'metrics': {
                'bandwidth_usage': 0,
                'latency': 0,
                'packet_loss': 0
            }
        })

    @route('node_start', '/nodes/{node_id}/start', methods=['POST'])
    def node_start(self, req, node_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        return self._json_response({
            "status": "success",
            "message": "Node started successfully",
            "node_id": node_id
        })

    @route('node_stop', '/nodes/{node_id}/stop', methods=['POST'])
    def node_stop(self, req, node_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        return self._json_response({
            "status": "success",
            "message": "Node stopped successfully",
            "node_id": node_id
        })

    @route('node_restart', '/nodes/{node_id}/restart', methods=['POST'])
    def node_restart(self, req, node_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        return self._json_response({
            "status": "success",
            "message": "Node restarted successfully",
            "node_id": node_id
        })

    @route('link_enable', '/links/{link_id}/enable', methods=['POST'])
    def link_enable(self, req, link_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        return self._json_response({
            "status": "success",
            "message": "Link enabled successfully",
            "link_id": link_id
        })

    @route('link_disable', '/links/{link_id}/disable', methods=['POST'])
    def link_disable(self, req, link_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        return self._json_response({
            "status": "success",
            "message": "Link disabled successfully",
            "link_id": link_id
        })

    # --- Policy Management ---

    @route('policy_create', '/policies', methods=['POST'])
    def create_policy(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        
        try:
            body = req.json if req.body else {}
            policy_data = body.get('policy')
            if not policy_data:
                raise ValueError("Missing policy data")
        except ValueError:
            return self._json_response({'code': '400', 'message': 'Invalid JSON or missing policy data'}, status=400)

        policy_id = self.sdn_controller.policy.create_policy(policy_data)
        
        # Clear flows to enforce new policy immediately
        self.sdn_controller.clear_all_flows()

        return self._json_response({
            "status": "success",
            "message": "Policy created successfully",
            "policy_id": policy_id
        }, status=201)

    @route('policy_get', '/policies/{policy_id}', methods=['GET'])
    def get_policy(self, req, policy_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        policy = self.sdn_controller.policy.get_policy(policy_id)
        if not policy:
             return self._json_response({'code': '404', 'message': 'Policy not found'}, status=404)

        return self._json_response({"policy": policy})

    @route('policy_update', '/policies/{policy_id}', methods=['PUT'])
    def update_policy(self, req, policy_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        try:
            body = req.json if req.body else {}
            policy_data = body.get('policy')
            if not policy_data:
                raise ValueError("Missing policy data")
        except ValueError:
            return self._json_response({'code': '400', 'message': 'Invalid JSON or missing policy data'}, status=400)

        if self.sdn_controller.policy.update_policy(policy_id, policy_data):
            return self._json_response({
                "status": "success",
                "message": "Policy updated successfully",
                "policy_id": policy_id
            })
        else:
             return self._json_response({'code': '404', 'message': 'Policy not found'}, status=404)

    @route('policy_delete', '/policies/{policy_id}', methods=['DELETE'])
    def delete_policy(self, req, policy_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        if self.sdn_controller.policy.delete_policy(policy_id):
            # Clear flows to remove enforcement of deleted policy
            self.sdn_controller.clear_all_flows()
            
            return self._json_response({
                "status": "success",
                "message": "Policy deleted successfully",
                "policy_id": policy_id
            })
        else:
             return self._json_response({'code': '404', 'message': 'Policy not found'}, status=404)

    @route('policy_apply', '/policies/{policy_id}/apply', methods=['POST'])
    def apply_policy(self, req, policy_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)
        
        policy = self.sdn_controller.policy.get_policy(policy_id)
        if not policy:
             return self._json_response({'code': '404', 'message': 'Policy not found'}, status=404)

        # Here we would implement actual logic to apply policy to switches
        # For now, just mark it as applied/active in metadata or status
        self.sdn_controller.policy.update_policy(policy_id, {'status': 'active'})

        return self._json_response({
            "status": "success",
            "message": "Policy applied successfully",
            "policy_id": policy_id
        })

    @route('policy_revoke', '/policies/{policy_id}/revoke', methods=['POST'])
    def revoke_policy(self, req, policy_id, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        policy = self.sdn_controller.policy.get_policy(policy_id)
        if not policy:
             return self._json_response({'code': '404', 'message': 'Policy not found'}, status=404)

        self.sdn_controller.policy.update_policy(policy_id, {'status': 'inactive'})

        return self._json_response({
            "status": "success",
            "message": "Policy revoked successfully",
            "policy_id": policy_id
        })

    @route('policy_list', '/policies', methods=['GET'])
    def list_policies(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        return self._json_response({
            "policies": self.sdn_controller.policy.list_policies()
        })

    # --- Statistics & Monitoring ---

    @route('stats_nodes', '/nodes/stats', methods=['GET'])
    def get_node_stats(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        stats = []
        # Real stats for switches
        for dpid in self.sdn_controller.topology.switches:
            throughput = 0.0
            if dpid in self.sdn_controller.traffic.port_stats:
                for port_stat in self.sdn_controller.traffic.port_stats[dpid].values():
                    throughput += port_stat['tx_bandwidth'] + port_stat['rx_bandwidth']

            stats.append({
                "node_id": str(dpid),
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "cpu_usage": 0, # Not available via OpenFlow
                "memory_usage": 0, # Not available via OpenFlow
                "network_throughput": throughput
            })
        return self._json_response({"stats": stats})

    @route('stats_links', '/links/stats', methods=['GET'])
    def get_link_stats(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        stats = []
        # Real stats for links
        for (u, v) in self.sdn_controller.topology.net.edges():
            bandwidth_usage = 0.0
            edge_data = self.sdn_controller.topology.net.get_edge_data(u, v)
            
            if edge_data and 'port' in edge_data:
                # Try to get stats from u (if u is a switch)
                if u in self.sdn_controller.traffic.port_stats:
                    port = edge_data['port'].get(u)
                    if port:
                        stat = self.sdn_controller.traffic.port_stats[u].get(port)
                        if stat:
                            bandwidth_usage = stat['tx_bandwidth'] + stat['rx_bandwidth']
                # If u is not a switch or no stats, try v (if v is a switch)
                elif v in self.sdn_controller.traffic.port_stats:
                    port = edge_data['port'].get(v)
                    if port:
                        stat = self.sdn_controller.traffic.port_stats[v].get(port)
                        if stat:
                            bandwidth_usage = stat['tx_bandwidth'] + stat['rx_bandwidth']

            stats.append({
                "link_id": "{}-{}".format(u, v),
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "bandwidth_usage": bandwidth_usage,
                "latency": 0.0, # Requires active probing
                "packet_loss": 0.0
            })
        return self._json_response({"stats": stats})

    @route('alerts', '/alerts', methods=['GET'])
    def get_alerts(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        return self._json_response({
            "alerts": []
        })

    @route('honeypot_logs', '/honeypot/logs', methods=['GET'])
    def get_honeypot_logs(self, req, **kwargs):
        if not self._verify_token(req):
            return self._json_response({'code': '401', 'message': 'Unauthorized'}, status=401)

        return self._json_response({
            "logs": []
        })

    # --- WebSockets ---

    @websocket('ws_network_status', '/ws/network-status')
    def ws_network_status(self, ws):
        self._ws_handler(ws, 'network-status')

    @websocket('ws_honeypot_alerts', '/ws/honeypot-alerts')
    def ws_honeypot_alerts(self, ws):
        self._ws_handler(ws, 'honeypot-alerts')

    @websocket('ws_flow_updates', '/ws/flow-updates')
    def ws_flow_updates(self, ws):
        self._ws_handler(ws, 'flow-updates')

    @websocket('ws_traffic_anomalies', '/ws/traffic-anomalies')
    def ws_traffic_anomalies(self, ws):
        self._ws_handler(ws, 'traffic-anomalies')

    @websocket('ws_topology_changes', '/ws/topology-changes')
    def ws_topology_changes(self, ws):
        self._ws_handler(ws, 'topology-changes')

    def _ws_handler(self, ws, channel):
        self.sdn_controller.notification.register_client(channel, ws)
        try:
            while True:
                # Keep connection alive
                hub.sleep(1)
        except Exception:
            pass
        finally:
            self.sdn_controller.notification.remove_client(channel, ws)

