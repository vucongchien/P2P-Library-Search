/**
 * API client wrapper cho Dashboard Frontend
 * Tương tác với backend aggregator tại /api/*
 */

const API_BASE = '/api';

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    const data = await response.json();
    return { data, error: null, status: response.status };
  } catch (error) {
    console.error(`Error fetching ${endpoint}:`, error);
    return { data: null, error: error.message, status: 500 };
  }
}

export const api = {
  // State 
  getPeers: () => fetchAPI('/peers'),
  addPeer: (nodeId, url) => fetchAPI('/peers/add', { 
    method: 'POST', 
    body: JSON.stringify({ node_id: parseInt(nodeId), url: url }) 
  }),
  getRingState: () => fetchAPI('/ring-state'),
  getMetrics: () => fetchAPI('/metrics'),
  getMessages: (since = 0) => fetchAPI(`/messages/all?since_global=${since}&limit=100`),
  
  // Setup & Orchestration 
  registerPeers: () => fetchAPI('/setup/register', { method: 'POST' }),
  joinRing: () => fetchAPI('/setup/join', { method: 'POST' }),
  stabilizeRing: (rounds = 8) => fetchAPI('/setup/stabilize', { 
    method: 'POST', 
    body: JSON.stringify({ rounds }) 
  }),
  publishData: () => fetchAPI('/setup/publish', { method: 'POST' }),
  uploadContent: (nodeId, title, content) => fetchAPI(`/upload/${nodeId}`, {
    method: 'POST',
    body: JSON.stringify({ title, content })
  }),
  fetchContent: (docId) => fetchAPI(`/content/${docId}`),
  
  // Query
  queryNetwork: (queryText, initiatorId = null) => fetchAPI('/query', {
    method: 'POST',
    body: JSON.stringify({ query: queryText, initiator_node_id: initiatorId })
  }),
  
  // Churn / Topology Updates
  removeNode: (nodeId) => fetchAPI('/churn/remove', {
    method: 'POST',
    body: JSON.stringify({ node_id: parseInt(nodeId, 10) })
  }),
  stabilizeAfterChurn: () => fetchAPI('/churn/stabilize-all', { method: 'POST' })
};
