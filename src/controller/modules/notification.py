import json
import logging
from datetime import datetime

class NotificationManager:
    def __init__(self):
        self.logger = logging.getLogger('NotificationManager')
        self.ws_clients = {
            'network-status': [],
            'node-metrics': [],
            'honeypot-alerts': [],
            'flow-updates': [],
            'traffic-anomalies': [],
            'topology-changes': []
        }

    def register_client(self, channel, ws):
        if channel not in self.ws_clients:
            self.ws_clients[channel] = []
        self.ws_clients[channel].append(ws)

    def remove_client(self, channel, ws):
        if channel in self.ws_clients and ws in self.ws_clients[channel]:
            self.ws_clients[channel].remove(ws)

    def broadcast(self, channel, payload):
        """Broadcast message to specific WebSocket channel"""
        # Log the pushed content as requested
        if channel == 'flow-updates':
            # Flow updates can be frequent, maybe summarize or log full if user wants "content pushed"
            # To avoid flooding console with massive JSON, we might want to be concise for flows
            # But user asked to see what is pushed.
            data = payload.get('data', {})
            flow_obj = data.get('flow', {})
            flow_id = flow_obj.get('flow_id') or flow_obj.get('id', 'unknown')
            rate = flow_obj.get('pkt_rate', 0)
            self.logger.info(f"PUSH [FLOW] ID={flow_id} Rate={rate:.2f}")
        elif channel in ['node-metrics', 'network-status']:
            # Suppress verbose logs for metrics and status to focus on flows
            pass
        else:
            self.logger.info(f"PUSH [{channel.upper()}] {json.dumps(payload)}")

        if channel in self.ws_clients:
            msg = json.dumps(payload)
            to_remove = []
            for ws in self.ws_clients[channel]:
                try:
                    ws.send(msg)
                except Exception:
                    to_remove.append(ws)
            for ws in to_remove:
                self.ws_clients[channel].remove(ws)

    def push_topology_change(self, change_type, data):
        payload = {
            'event': 'topology_change',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'change_type': change_type,
                **data
            }
        }
        self.broadcast('topology-changes', payload)

    def push_network_status(self, node_data):
        # node_data: {node_id, status}
        payload = {
            'event': 'network_status_update',
            'timestamp': datetime.utcnow().isoformat(),
            'data': node_data
        }
        self.broadcast('network-status', payload)

    def push_node_metrics(self, node_id, metrics):
        payload = {
            'event': 'node_metrics_update',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'node_id': node_id,
                'metrics': metrics
            }
        }
        self.broadcast('node-metrics', payload)

    def push_traffic_anomaly(self, flow_id, details):
        payload = {
            'event': 'traffic_anomaly',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'flow_id': flow_id,
                **details
            }
        }
        self.broadcast('traffic-anomalies', payload)

    def push_honeypot_alert(self, source_ip, details):
        payload = {
            'event': 'honeypot_interaction',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'source_ip': source_ip,
                **details
            }
        }
        self.broadcast('honeypot-alerts', payload)

    def push_flow_update(self, flow_data):
        payload = {
            'event': 'flow_update',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {'flow': flow_data}
        }
        self.broadcast('flow-updates', payload)
