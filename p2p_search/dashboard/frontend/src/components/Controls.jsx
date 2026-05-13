import React, { useState } from 'react';
import { Network, Link2, GitMerge, UploadCloud, Trash2 } from 'lucide-react';
import { api } from '../api';

export function Controls({ peers, refreshData }) {
  const [loading, setLoading] = useState(false);

  const handleAction = async (actionFn, successMsg) => {
    setLoading(true);
    try {
      await actionFn();
      // Wait a moment for network to propagate, then refresh
      setTimeout(() => {
        refreshData();
        setLoading(false);
      }, 500);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200 mb-6">
      <h2 className="text-lg font-semibold mb-4 text-slate-800 border-b pb-2">Network Setup & Controls</h2>
      
      <div className="flex flex-wrap gap-3">
        <button 
          disabled={loading}
          onClick={() => handleAction(api.registerPeers, "Registered")}
          className="flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 rounded-md text-sm font-medium transition-colors"
        >
          <Network size={16} /> 1. Register Peers
        </button>
        
        <button 
          disabled={loading}
          onClick={() => handleAction(api.joinRing, "Joined")}
          className="flex items-center gap-2 px-3 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-md text-sm font-medium transition-colors"
        >
          <Link2 size={16} /> 2. Join Ring
        </button>
        
        <button 
          disabled={loading}
          onClick={() => handleAction(() => api.stabilizeRing(8), "Stabilized")}
          className="flex items-center gap-2 px-3 py-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 rounded-md text-sm font-medium transition-colors"
        >
          <GitMerge size={16} /> 3. Stabilize
        </button>
        
        <button 
          disabled={loading}
          onClick={() => handleAction(api.publishData, "Published")}
          className="flex items-center gap-2 px-3 py-2 bg-violet-50 text-violet-700 hover:bg-violet-100 border border-violet-200 rounded-md text-sm font-medium transition-colors"
        >
          <UploadCloud size={16} /> 4. Publish Dataset
        </button>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-100 flex flex-col gap-3">
        <span className="text-sm font-semibold text-slate-700">Professor Demo: Dynamic Join</span>
        <div className="flex items-center gap-2">
          <input 
            id="new-node-id" 
            type="number" 
            placeholder="Node ID" 
            className="w-24 text-sm border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none" 
          />
          <input 
            id="new-node-url" 
            type="text" 
            placeholder="Port (e.g. :8006)" 
            className="w-36 text-sm border border-slate-300 rounded px-3 py-1.5 focus:ring-1 focus:ring-blue-500 outline-none" 
          />
          <button 
             disabled={loading}
             onClick={() => {
                const id = document.getElementById('new-node-id').value;
                const port = document.getElementById('new-node-url').value;
                if (id && port) {
                  const fullUrl = port.startsWith('http') ? port : `http://127.0.0.1${port.startsWith(':') ? '' : ':'}${port}`;
                  handleAction(() => api.addPeer(id, fullUrl), "New peer registered in dashboard");
                  document.getElementById('new-node-id').value = '';
                  document.getElementById('new-node-url').value = '';
                }
             }}
             className="px-4 py-1.5 bg-slate-800 text-white rounded-md text-sm font-medium hover:bg-slate-700 transition-colors"
          >
            Add Peer to Dashboard
          </button>
          <p className="text-[10px] text-slate-400 max-w-[200px] leading-tight">
            * Step 1: Run peer_server.py in a new terminal. <br/>
            * Step 2: Add it here. <br/>
            * Step 3: Click <b>Join</b> on its card.
          </p>
        </div>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-100 flex items-center gap-3">
        <span className="text-sm font-medium text-slate-700">Simulate Churn:</span>
        <select id="churn-select" className="text-sm border border-slate-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500">
          <option value="">Select Peer to Kill</option>
          {peers.filter(p => p.alive).map(p => (
            <option key={p.node_id} value={p.node_id}>Node {p.node_id}</option>
          ))}
        </select>
        <button 
          disabled={loading}
          onClick={() => {
            const select = document.getElementById('churn-select');
            if (select.value) {
              handleAction(() => api.removeNode(select.value), "Removed");
              select.value = '';
            }
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 rounded-md text-sm font-medium transition-colors"
        >
          <Trash2 size={14} /> Remove Node
        </button>
        <button 
           disabled={loading}
           onClick={() => handleAction(api.stabilizeAfterChurn, "Stabilized")}
           className="ml-auto text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded border border-slate-300 transition-colors font-medium"
        >
          Heal Ring (Stabilize)
        </button>
      </div>
    </div>
  );
}
