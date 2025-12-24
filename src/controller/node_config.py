
SWITCHES = {
    # Core Layer
    '0000000000000001': {'name': 's_core1', 'zone': 'Core'},
    '0000000000000002': {'name': 's_core2', 'zone': 'Core'},
    
    # Aggregation Layer
    '0000000000000011': {'name': 's_agg_a', 'zone': 'Zone A'}, # Manufacturing
    '0000000000000012': {'name': 's_agg_b', 'zone': 'Zone B'}, # Assembly
    '0000000000000013': {'name': 's_agg_c', 'zone': 'Control Room'}, # Control Room
    '0000000000000014': {'name': 's_agg_d', 'zone': 'DMZ'},    # DMZ

    # Access Layer
    '0000000000000021': {'name': 's_acc_a1', 'zone': 'Zone A'},
    '0000000000000022': {'name': 's_acc_b1', 'zone': 'Zone B'},
    '0000000000000023': {'name': 's_acc_c1', 'zone': 'Control Room'},
    '0000000000000024': {'name': 's_acc_d1', 'zone': 'DMZ'},
}

HOSTS = {
    # Zone A: Manufacturing (PLC, HMI, Sensors)
    '00:00:00:00:00:01': {'name': 'hmi1', 'ip': '10.0.1.10/16', 'type': 'hmi', 'zone': 'Zone A'},
    '00:00:00:00:00:02': {'name': 'plc1', 'ip': '10.0.1.20/16', 'type': 'plc', 'zone': 'Zone A'},
    '00:00:00:00:00:03': {'name': 'sensor1', 'ip': '10.0.1.30/16', 'type': 'sensor', 'zone': 'Zone A'},

    # Zone B: Assembly (Robots, PLC, HMI)
    '00:00:00:00:00:04': {'name': 'hmi2', 'ip': '10.0.2.10/16', 'type': 'hmi', 'zone': 'Zone B'},
    '00:00:00:00:00:05': {'name': 'plc2', 'ip': '10.0.2.20/16', 'type': 'plc', 'zone': 'Zone B'},
    '00:00:00:00:00:06': {'name': 'robot1', 'ip': '10.0.2.30/16', 'type': 'actuator', 'zone': 'Zone B'},

    # Zone C: Control Room (SCADA, Workstations)
    '00:00:00:00:00:07': {'name': 'scada', 'ip': '10.0.3.10/16', 'type': 'server', 'zone': 'Control Room'},
    '00:00:00:00:00:08': {'name': 'ws1', 'ip': '10.0.3.20/16', 'type': 'workstation', 'zone': 'Control Room'},

    # DMZ: External Access / Historian
    '00:00:00:00:00:09': {'name': 'historian', 'ip': '10.0.4.10/16', 'type': 'database', 'zone': 'DMZ'},
    '00:00:00:00:00:10': {'name': 'web_portal', 'ip': '10.0.4.20/16', 'type': 'server', 'zone': 'DMZ'},
}

