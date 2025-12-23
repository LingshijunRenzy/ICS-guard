const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const jwt = require('jsonwebtoken');
const { v4: uuidv4 } = require('uuid');
const http = require('http');
const WebSocket = require('ws');

const app = express();
const PORT = process.env.PORT || 8000;

// Create HTTP server for WebSocket
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// Mock data
const mockData = {
  nodes: [
    { id: 'sw1', name: 'Switch1', type: 'switch', ip: '10.0.0.1', status: 'online' },
    { id: 'plc1', name: 'PLC1', type: 'plc', ip: '10.0.0.10', status: 'online' },
    { id: 'hp1', name: 'Honeypot1', type: 'honeypot', ip: '10.0.0.20', status: 'online' },
    { id: 'plc2', name: 'PLC2', type: 'plc', ip: '10.0.0.11', status: 'online' },
    { id: 'hmi1', name: 'HMI1', type: 'hmi', ip: '10.0.0.30', status: 'online' }
  ],
  links: [
    { id: 'l1', source: 'sw1', target: 'plc1', bandwidth: 100, status: 'active' },
    { id: 'l2', source: 'sw1', target: 'hp1', bandwidth: 100, status: 'active' },
    { id: 'l3', source: 'sw1', target: 'plc2', bandwidth: 100, status: 'active' },
    { id: 'l4', source: 'sw1', target: 'hmi1', bandwidth: 100, status: 'active' }
  ],
  policies: [
    {
      id: 'p1',
      name: 'Default Access Control',
      description: 'Default access control policy',
      type: 'node',
      subtype: 'access_control',
      status: 'active',
      priority: 1,
      scope: { target_type: 'device', target_identifier: 'all' },
      conditions: {
        trigger_thresholds: {
          cpu_usage: 90,
          memory_usage: 85,
          network_throughput: 950,
          latency: 50,
          packet_loss: 5
        },
        protocol_specific: {
          func_code_entropy: 0.8,
          reg_addr_std: 100
        }
      },
      actions: {
        primary_action: 'allow',
        secondary_actions: ['log', 'alert']
      },
      monitoring: {
        stats_enabled: true,
        alert_thresholds: {
          high: 80,
          medium: 50,
          low: 20
        },
        health_check: {
          interval: 30000,
          timeout: 5000
        }
      },
      metadata: { created_by: 'system', created_at: '2023-01-01T00:00:00Z' }
    }
  ],
  flows: [
    {
      id: 'flow_1',
      src_ip: '10.0.0.10',
      dst_ip: '10.0.0.30',
      src_port: 502,
      dst_port: 502,
      protocol: 'modbus',
      start_time: new Date(Date.now() - 3600000).toISOString(),
      end_time: new Date().toISOString(),
      duration: 3600,
      pkt_count: 1000,
      byte_count: 100000,
      pkt_rate: 10,
      byte_rate: 1000,
      func_code_entropy: 0.2,
      reg_addr_std: 50,
      status: 'active'
    },
    {
      id: 'flow_2',
      src_ip: '10.0.0.11',
      dst_ip: '10.0.0.30',
      src_port: 502,
      dst_port: 502,
      protocol: 'modbus',
      start_time: new Date(Date.now() - 1800000).toISOString(),
      end_time: new Date().toISOString(),
      duration: 1800,
      pkt_count: 500,
      byte_count: 50000,
      pkt_rate: 5,
      byte_rate: 500,
      func_code_entropy: 0.3,
      reg_addr_std: 60,
      status: 'active'
    }
  ]
};

// WebSocket clients grouped by topic
const clients = {
  'network-status': new Set(),
  'traffic-anomalies': new Set(),
  'honeypot-alerts': new Set(),
  'topology-changes': new Set(),
  'flow-updates': new Set()
};

// Middleware
app.use(cors());
app.use(bodyParser.json());

// Generate mock statistics
const generateMockStats = (type, count = 5) => {
  const stats = [];
  const now = new Date();
  
  for (let i = 0; i < count; i++) {
    const timestamp = new Date(now.getTime() - i * 60000).toISOString();
    
    if (type === 'node') {
      mockData.nodes.forEach(node => {
        stats.push({
          node_id: node.id,
          timestamp,
          cpu_usage: Math.random() * 100,
          memory_usage: Math.random() * 100,
          network_throughput: Math.random() * 1000
        });
      });
    } else if (type === 'link') {
      mockData.links.forEach(link => {
        stats.push({
          link_id: link.id,
          timestamp,
          bandwidth_usage: Math.random() * 100,
          latency: Math.random() * 100,
          packet_loss: Math.random() * 10
        });
      });
    }
  }
  
  return stats;
};

// Generate JWT token
const generateToken = (clientId) => {
  const accessToken = jwt.sign({ client_id: clientId }, 'secret_key', { expiresIn: '1h' });
  const refreshToken = jwt.sign({ client_id: clientId }, 'refresh_secret', { expiresIn: '7d' });
  return { access_token: accessToken, token_type: 'Bearer', expires_in: 3600, refresh_token: refreshToken };
};

// Auth middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (token == null) return res.status(401).json({
    code: '401',
    message: '缺少或无效的认证'
  });
  
  jwt.verify(token, 'secret_key', (err, user) => {
    if (err) return res.status(403).json({
      code: '403',
      message: '权限不足'
    });
    
    req.user = user;
    next();
  });
};

// API Response wrapper
const wrapResponse = (data, code = '200', message = '请求成功') => {
  return {
    code,
    message,
    metadata: {
      timestamp: new Date().toISOString()
    },
    data
  };
};

// Auth APIs

// 获取访问令牌
app.post('/auth/token', (req, res) => {
  const { client_id, client_secret } = req.body;
  
  if (!client_id || !client_secret) {
    return res.status(400).json({
      code: '400',
      message: '缺少必需参数'
    });
  }
  
  // Mock authentication - in real implementation, you would validate against a database
  if (client_id && client_secret) {
    const tokens = generateToken(client_id);
    res.json(wrapResponse(tokens));
  } else {
    res.status(401).json({
      code: '401',
      message: '客户端凭证无效'
    });
  }
});

// 刷新访问令牌
app.get('/auth/refresh', (req, res) => {
  const authHeader = req.headers['authorization'];
  const refreshToken = authHeader && authHeader.split(' ')[1];
  
  if (!refreshToken) {
    return res.status(400).json({
      code: '400',
      message: '缺少必需参数'
    });
  }
  
  jwt.verify(refreshToken, 'refresh_secret', (err, user) => {
    if (err) return res.status(401).json({
      code: '401',
      message: '刷新令牌无效或过期'
    });
    
    const newTokens = generateToken(user.client_id);
    res.json(wrapResponse(newTokens));
  });
});

// 验证令牌
app.post('/auth/verify', (req, res) => {
  const { token } = req.body;
  
  if (!token) {
    return res.status(400).json({
      code: '400',
      message: '缺少必需参数'
    });
  }
  
  jwt.verify(token, 'secret_key', (err, user) => {
    if (err) return res.status(401).json({
      code: '401',
      message: '令牌无效或过期'
    });
    
    res.json(wrapResponse({
      valid: true,
      client_id: user.client_id,
      expires_at: new Date(Date.now() + 3600000).toISOString()
    }));
  });
});

// 撤销令牌
app.post('/auth/revoke', (req, res) => {
  const { token } = req.body;
  
  if (!token) {
    return res.status(400).json({
      code: '400',
      message: '缺少必需参数'
    });
  }
  
  // Mock revoke - in real implementation, you would add to a blacklist
  res.json(wrapResponse({ revoked: true }));
});

// Topology APIs

// 获取网络拓扑信息
app.get('/topology', authenticateToken, (req, res) => {
  const topology = {
    nodes: mockData.nodes,
    links: mockData.links
  };
  res.json(wrapResponse(topology));
});

// Status APIs

// 获取节点状态
app.get('/nodes/:node_id/status', authenticateToken, (req, res) => {
  const { node_id } = req.params;
  const node = mockData.nodes.find(n => n.id === node_id);
  
  if (!node) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  const status = {
    node_id: node.id,
    status: node.status,
    last_updated: new Date().toISOString(),
    metrics: {
      cpu_usage: Math.random() * 100,
      memory_usage: Math.random() * 100,
      network_throughput: Math.random() * 1000
    }
  };
  
  res.json(wrapResponse(status));
});

// 获取连接状态
app.get('/links/:link_id/status', authenticateToken, (req, res) => {
  const { link_id } = req.params;
  const link = mockData.links.find(l => l.id === link_id);
  
  if (!link) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  const status = {
    link_id: link.id,
    status: link.status,
    last_updated: new Date().toISOString(),
    metrics: {
      bandwidth_usage: Math.random() * 100,
      latency: Math.random() * 100,
      packet_loss: Math.random() * 10
    }
  };
  
  res.json(wrapResponse(status));
});

// Node operation APIs

// 启动节点
app.post('/nodes/:node_id/start', authenticateToken, (req, res) => {
  const { node_id } = req.params;
  const node = mockData.nodes.find(n => n.id === node_id);
  
  if (!node) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  node.status = 'online';
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Node started successfully',
    node_id: node.id
  }));
});

// 停止节点
app.post('/nodes/:node_id/stop', authenticateToken, (req, res) => {
  const { node_id } = req.params;
  const node = mockData.nodes.find(n => n.id === node_id);
  
  if (!node) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  node.status = 'offline';
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Node stopped successfully',
    node_id: node.id
  }));
});

// 重启节点
app.post('/nodes/:node_id/restart', authenticateToken, (req, res) => {
  const { node_id } = req.params;
  const node = mockData.nodes.find(n => n.id === node_id);
  
  if (!node) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  // Simulate restart
  node.status = 'online';
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Node restarted successfully',
    node_id: node.id
  }));
});

// Link operation APIs

// 启用连接
app.post('/links/:link_id/enable', authenticateToken, (req, res) => {
  const { link_id } = req.params;
  const link = mockData.links.find(l => l.id === link_id);
  
  if (!link) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  link.status = 'active';
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Link enabled successfully',
    link_id: link.id
  }));
});

// 禁用连接
app.post('/links/:link_id/disable', authenticateToken, (req, res) => {
  const { link_id } = req.params;
  const link = mockData.links.find(l => l.id === link_id);
  
  if (!link) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  link.status = 'inactive';
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Link disabled successfully',
    link_id: link.id
  }));
});

// Policy APIs

// 创建策略
app.post('/policies', authenticateToken, (req, res) => {
  const { policy } = req.body;
  const newPolicy = {
    ...policy,
    id: policy.id || uuidv4(),
    metadata: {
      ...policy.metadata,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
  };
  
  mockData.policies.push(newPolicy);
  
  res.status(201).json(wrapResponse({
    status: 'success',
    message: 'Policy created successfully',
    policy_id: newPolicy.id
  }));
});

// 获取策略
app.get('/policies/:policy_id', authenticateToken, (req, res) => {
  const { policy_id } = req.params;
  const policy = mockData.policies.find(p => p.id === policy_id);
  
  if (!policy) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  res.json(wrapResponse({ policy }));
});

// 更新策略
app.put('/policies/:policy_id', authenticateToken, (req, res) => {
  const { policy_id } = req.params;
  const { policy: updatedPolicy } = req.body;
  const index = mockData.policies.findIndex(p => p.id === policy_id);
  
  if (index === -1) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  mockData.policies[index] = {
    ...mockData.policies[index],
    ...updatedPolicy,
    metadata: {
      ...mockData.policies[index].metadata,
      updated_at: new Date().toISOString()
    }
  };
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Policy updated successfully',
    policy_id: policy_id
  }));
});

// 删除策略
app.delete('/policies/:policy_id', authenticateToken, (req, res) => {
  const { policy_id } = req.params;
  const index = mockData.policies.findIndex(p => p.id === policy_id);
  
  if (index === -1) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  mockData.policies.splice(index, 1);
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Policy deleted successfully',
    policy_id: policy_id
  }));
});

// 应用策略
app.post('/policies/:policy_id/apply', authenticateToken, (req, res) => {
  const { policy_id } = req.params;
  const policy = mockData.policies.find(p => p.id === policy_id);
  
  if (!policy) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Policy applied successfully',
    policy_id: policy_id
  }));
});

// 撤销策略
app.post('/policies/:policy_id/revoke', authenticateToken, (req, res) => {
  const { policy_id } = req.params;
  const policy = mockData.policies.find(p => p.id === policy_id);
  
  if (!policy) {
    return res.status(404).json(wrapResponse({}, '404', '资源未找到'));
  }
  
  res.json(wrapResponse({
    status: 'success',
    message: 'Policy revoked successfully',
    policy_id: policy_id
  }));
});

// 列出所有策略
app.get('/policies', authenticateToken, (req, res) => {
  const { type, status } = req.query;
  let filteredPolicies = [...mockData.policies];
  
  if (type) {
    filteredPolicies = filteredPolicies.filter(p => p.type === type);
  }
  
  if (status) {
    filteredPolicies = filteredPolicies.filter(p => p.status === status);
  }
  
  res.json(wrapResponse({ policies: filteredPolicies }));
});

// Statistics APIs

// 获取节点性能统计
app.get('/nodes/stats', authenticateToken, (req, res) => {
  const { start_time, end_time } = req.query;
  const stats = generateMockStats('node', 10);
  res.json(wrapResponse({ stats }));
});

// 获取连接性能统计
app.get('/links/stats', authenticateToken, (req, res) => {
  const { start_time, end_time } = req.query;
  const stats = generateMockStats('link', 10);
  res.json(wrapResponse({ stats }));
});

// 获取安全告警
app.get('/alerts', authenticateToken, (req, res) => {
  const { start_time, end_time, severity } = req.query;
  
  // Generate mock alerts
  const alerts = [];
  const severities = ['low', 'medium', 'high'];
  const alertTypes = ['intrusion_attempt', 'policy_violation', 'network_anomaly'];
  
  for (let i = 0; i < 10; i++) {
    const alertSeverity = severity || severities[Math.floor(Math.random() * severities.length)];
    if (!severity || alertSeverity === severity) {
      alerts.push({
        id: `alert_${i}`,
        timestamp: new Date(Date.now() - i * 3600000).toISOString(),
        type: alertTypes[Math.floor(Math.random() * alertTypes.length)],
        severity: alertSeverity,
        source_ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        description: `Mock alert description ${i}`
      });
    }
  }
  
  res.json(wrapResponse({ alerts }));
});

// 获取蜜罐日志
app.get('/honeypot/logs', authenticateToken, (req, res) => {
  const { start_time, end_time } = req.query;
  
  // Generate mock honeypot logs
  const logs = [];
  
  for (let i = 0; i < 10; i++) {
    logs.push({
      id: `log_${i}`,
      timestamp: new Date(Date.now() - i * 3600000).toISOString(),
      source_ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
      request: `GET /admin HTTP/1.1`,
      response: `HTTP/1.1 403 Forbidden`
    });
  }
  
  res.json(wrapResponse({ logs }));
});

// WebSocket API implementation

// Authenticate WebSocket connection
const authenticateWebSocket = (token) => {
  try {
    jwt.verify(token, 'secret_key');
    return true;
  } catch (err) {
    return false;
  }
};

// Handle WebSocket connections
wss.on('connection', (ws, req) => {
  // Extract token from query parameters
  const urlParams = new URLSearchParams(req.url.split('?')[1]);
  const token = urlParams.get('token');
  
  // Authenticate
  if (!token || !authenticateWebSocket(token)) {
    ws.close(4001, 'Authentication failed');
    return;
  }
  
  // Extract topic from URL
  const path = req.url.split('?')[0];
  const topic = path.replace('/ws/', '');
  
  // Check if topic is valid
  if (clients[topic]) {
    // Add client to topic group
    clients[topic].add(ws);
    
    // Handle client disconnection
    ws.on('close', () => {
      clients[topic].delete(ws);
    });
  } else {
    ws.close(4002, 'Invalid topic');
  }
});

// Function to send message to all clients in a topic
const broadcast = (topic, message) => {
  const jsonMessage = JSON.stringify(message);
  clients[topic].forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(jsonMessage);
    }
  });
};

// Generate network status update
const generateNetworkStatusUpdate = () => {
  const node = mockData.nodes[Math.floor(Math.random() * mockData.nodes.length)];
  const statuses = ['online', 'offline', 'warning', 'error'];
  const newStatus = statuses[Math.floor(Math.random() * statuses.length)];
  
  // Update node status
  node.status = newStatus;
  
  return {
    event: 'network_status_update',
    timestamp: new Date().toISOString(),
    data: {
      node_id: node.id,
      status: newStatus
    }
  };
};

// Generate traffic anomaly
const generateTrafficAnomaly = () => {
  const flow = mockData.flows[Math.floor(Math.random() * mockData.flows.length)];
  
  return {
    event: 'traffic_anomaly',
    timestamp: new Date().toISOString(),
    data: {
      flow_id: flow.id,
      src_ip: flow.src_ip,
      dst_ip: flow.dst_ip,
      anomaly_score: Math.random() * 100,
      details: `High traffic detected: ${Math.round(Math.random() * 1000)} packets/sec`
    }
  };
};

// Generate honeypot alert
const generateHoneypotAlert = () => {
  return {
    event: 'honeypot_interaction',
    timestamp: new Date().toISOString(),
    data: {
      source_ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
      request: `GET /admin HTTP/1.1`,
      timestamp: new Date().toISOString()
    }
  };
};

// Generate topology change
const generateTopologyChange = () => {
  const changeTypes = ['node_added', 'node_removed', 'link_added', 'link_removed'];
  const changeType = changeTypes[Math.floor(Math.random() * changeTypes.length)];
  
  return {
    event: 'topology_change',
    timestamp: new Date().toISOString(),
    data: {
      change_type: changeType,
      details: {
        id: uuidv4(),
        name: `Device_${Math.floor(Math.random() * 100)}`,
        type: changeType.includes('node') ? ['switch', 'plc', 'hmi', 'honeypot'][Math.floor(Math.random() * 4)] : 'link'
      }
    }
  };
};

// Generate flow update
const generateFlowUpdate = () => {
  const flow = mockData.flows[Math.floor(Math.random() * mockData.flows.length)];
  
  // Update flow statistics
  flow.pkt_count += Math.floor(Math.random() * 100);
  flow.byte_count += Math.floor(Math.random() * 10000);
  flow.pkt_rate = Math.random() * 20;
  flow.byte_rate = Math.random() * 2000;
  
  return {
    event: 'flow_update',
    timestamp: new Date().toISOString(),
    data: {
      flow: flow
    }
  };
};

// Schedule periodic updates
setInterval(() => {
  broadcast('network-status', generateNetworkStatusUpdate());
}, 10000); // Every 10 seconds

setInterval(() => {
  broadcast('traffic-anomalies', generateTrafficAnomaly());
}, 15000); // Every 15 seconds

setInterval(() => {
  broadcast('honeypot-alerts', generateHoneypotAlert());
}, 20000); // Every 20 seconds

setInterval(() => {
  broadcast('topology-changes', generateTopologyChange());
}, 30000); // Every 30 seconds

setInterval(() => {
  broadcast('flow-updates', generateFlowUpdate());
}, 5000); // Every 5 seconds

// Start server
server.listen(PORT, () => {
  console.log(`ICS-Guard Mock Server running on port ${PORT}`);
  console.log('WebSocket endpoints available at:');
  console.log('  ws://localhost:8000/ws/network-status');
  console.log('  ws://localhost:8000/ws/traffic-anomalies');
  console.log('  ws://localhost:8000/ws/honeypot-alerts');
  console.log('  ws://localhost:8000/ws/topology-changes');
  console.log('  ws://localhost:8000/ws/flow-updates');
});
