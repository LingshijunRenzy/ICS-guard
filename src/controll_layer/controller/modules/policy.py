import logging
import time

class PolicyManager:
    def __init__(self):
        self.logger = logging.getLogger('PolicyManager')
        self.policies = {} # {policy_id: policy_dict}

    def create_policy(self, policy_data):
        policy_id = policy_data.get('id', 'policy_{}'.format(int(time.time())))
        policy_data['id'] = policy_id
        policy_data.setdefault('metadata', {})['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        policy_data['status'] = 'active' # Default to active for now
        
        self.policies[policy_id] = policy_data
        return policy_id

    def get_policy(self, policy_id):
        return self.policies.get(policy_id)

    def update_policy(self, policy_id, policy_data):
        if policy_id in self.policies:
            self.policies[policy_id].update(policy_data)
            self.policies[policy_id]['id'] = policy_id
            return True
        return False

    def delete_policy(self, policy_id):
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False

    def list_policies(self):
        return list(self.policies.values())

    def check_packet(self, dpid, src_mac, dst_mac, src_ip, dst_ip, protocol, dst_port):
        """
        Check if packet is allowed by policies.
        Returns: (action, reason)
        action: 'allow', 'drop', 'redirect'
        """
        # Default action if no policy matches
        final_action = 'allow'
        reason = None
        highest_priority = -1

        for policy in self.policies.values():
            if policy.get('status') != 'active':
                continue
            
            conditions = policy.get('conditions', {})
            match = True
            
            # 1. Source IP Match
            if 'src_ip' in conditions:
                if not src_ip or conditions['src_ip'] != src_ip:
                    match = False
            
            # 2. Destination IP Match
            if match and 'dst_ip' in conditions:
                if not dst_ip or conditions['dst_ip'] != dst_ip:
                    match = False

            # 3. Protocol Match (Case insensitive)
            if match and 'protocol' in conditions:
                if not protocol or conditions['protocol'].upper() != str(protocol).upper():
                    match = False

            # 4. Destination Port Match
            if match and 'dst_port' in conditions:
                if dst_port is None:
                    match = False
                else:
                    try:
                        target_port = int(conditions['dst_port'])
                        if target_port != dst_port:
                            match = False
                    except (ValueError, TypeError):
                        pass # Ignore invalid port config

            # 5. MAC Address Matching
            if match and 'src_mac' in conditions:
                if conditions['src_mac'] != src_mac:
                    match = False
            
            if match and 'dst_mac' in conditions:
                if conditions['dst_mac'] != dst_mac:
                    match = False

            if match:
                priority = int(policy.get('priority', 0))
                if priority > highest_priority:
                    highest_priority = priority
                    # Map 'deny'/'block' to 'drop'
                    act = policy.get('action', 'allow').lower()
                    if act in ['deny', 'block']:
                        final_action = 'drop'
                    else:
                        final_action = 'allow'
                    reason = policy.get('name', policy.get('id'))
        
        return final_action, reason
