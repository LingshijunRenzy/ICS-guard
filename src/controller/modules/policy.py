import logging
import time
import json
import uuid

class PolicyManager:
    def __init__(self):
        self.logger = logging.getLogger('PolicyManager')
        self.policies = {} # {policy_id: policy_dict}

    def create_policy(self, policy_data):
        policy_id = policy_data.get('id', f'policy_{uuid.uuid4().hex[:8]}')
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
        Returns: (action, reason, action_params)
        action: 'allow', 'drop', 'redirect', 'throttle'
        """
        # Default action if no policy matches
        final_action = 'allow'
        reason = None
        action_params = {}
        highest_priority = -1

        for policy in self.policies.values():
            if policy.get('status') != 'active':
                continue
            
            conditions = policy.get('conditions', {})
            # Robustness: Parse conditions if string
            if isinstance(conditions, str):
                try:
                    conditions = json.loads(conditions)
                except:
                    self.logger.warning("Failed to parse conditions JSON for policy %s", policy.get('id'))
                    conditions = {}

            match = True
            
            # 0. Scope / Target Check
            # Support 'target_id' at root or inside 'scope'
            target_id = policy.get('target_id')
            if not target_id:
                target_id = policy.get('scope', {}).get('target_id')
            
            if target_id and isinstance(target_id, str):
                target_id = target_id.strip()
            
            if target_id:
                # Policy only applies if the target is involved (Source or Destination)
                if src_mac != target_id and dst_mac != target_id:
                    match = False

            # 1. Source IP Match
            if match and 'src_ip' in conditions:
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

            # 6. Advanced Access Control (allowed_ips / denied_ips)
            if match and ('allowed_ips' in conditions or 'denied_ips' in conditions):
                # Identify remote IP (the one that is NOT the target)
                ips_to_check = []
                if target_id:
                    if src_mac == target_id: ips_to_check.append(dst_ip)
                    if dst_mac == target_id: ips_to_check.append(src_ip)
                else:
                    ips_to_check = [src_ip, dst_ip]
                
                # Check Denied List (Blacklist)
                is_denied = False
                if 'denied_ips' in conditions:
                    denied_list = conditions['denied_ips']
                    if isinstance(denied_list, str): denied_list = [denied_list]
                    for ip in ips_to_check:
                        if ip in denied_list or '*' in denied_list or '*.*.*.*' in denied_list:
                            is_denied = True
                            break
                
                # Check Allowed List (Whitelist)
                is_allowed = False
                if 'allowed_ips' in conditions:
                    allowed_list = conditions['allowed_ips']
                    if isinstance(allowed_list, str): allowed_list = [allowed_list]
                    for ip in ips_to_check:
                        if ip in allowed_list or '*' in allowed_list or '*.*.*.*' in allowed_list:
                            is_allowed = True
                            break
                else:
                    is_allowed = True

                # Conflict Resolution: Deny wins
                if is_denied:
                    match = True # Match the policy (BLOCK)
                elif not is_allowed:
                    match = True # Not in whitelist -> Match the policy (BLOCK)
                else:
                    match = False # Allowed and not denied -> Do NOT match this BLOCK policy

            # DEBUG LOG
            if policy.get('id', '').startswith('policy_'):
                 self.logger.info("Policy %s check: Match=%s, Conditions=%s, SrcIP=%s, DstIP=%s", policy.get('id'), match, conditions, src_ip, dst_ip)

            if match:
                priority = int(policy.get('priority', 0))
                if priority > highest_priority:
                    highest_priority = priority
                    
                    # Extract action from flat 'action' field or nested 'actions' object
                    act = policy.get('action')
                    current_params = {}
                    
                    if not act:
                        # Try nested structure: actions -> primary_action -> action_type
                        actions = policy.get('actions', {})
                        if isinstance(actions, dict):
                            primary = actions.get('primary_action', {})
                            if isinstance(primary, dict):
                                act = primary.get('action_type')
                                current_params = primary.get('action_params', {})
                            elif isinstance(primary, str):
                                act = primary # Handle case where primary_action might be just a string
                    
                    if not act:
                        act = 'allow' # Default

                    act = str(act).lower()

                    # Map actions
                    if act in ['deny', 'block', 'drop']:
                        final_action = 'drop'
                    elif act == 'throttle':
                        final_action = 'throttle'
                        # Extract rate limit params
                        # Check if params are in action_params (nested) or directly in actions (flat/legacy)
                        if 'rate_limit' in current_params:
                            action_params = current_params['rate_limit']
                        elif 'rate_limit' in policy.get('actions', {}):
                             action_params = policy.get('actions', {})['rate_limit']
                        else:
                             # Fallback or empty
                             action_params = current_params
                    elif act == 'redirect':
                        final_action = 'redirect'
                        if 'targets' in current_params:
                            action_params = current_params
                        elif 'redirect_target' in policy.get('actions', {}):
                             # Legacy/Flat support
                             action_params = {'targets': [{'ip': policy.get('actions', {})['redirect_target']}]}
                        else:
                             action_params = current_params
                    else:
                        final_action = 'allow'
                    
                    self.logger.info("Policy %s matched. Raw Action: '%s' -> Final Action: '%s'", policy.get('id'), act, final_action)

                    reason = policy.get('name', policy.get('id'))
        
        return final_action, reason, action_params
