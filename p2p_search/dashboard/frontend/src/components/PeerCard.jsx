import React, { useState } from 'react';
import { Server, ChevronDown, ChevronRight, Hash, HardDrive, Share2, Activity, Database, FileText, Upload } from 'lucide-react';
import { api } from '../api';

export function PeerList({ peers, states, activeTrace }) {
  const traceNodeIds = new Set();
  if (activeTrace) {
    activeTrace.forEach(hop => {
      traceNodeIds.add(hop.node);
      if (hop.next_node) traceNodeIds.add(hop.next_node);
    });
  }

  if (!peers || peers.length === 0) {
    return (
      <div className="h-64 break-all text-slate-400 border-2 border-dashed border-slate-200 rounded-md flex items-center justify-center">
        No peers connected. Start peer servers and register them.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {peers.map(peer => {
        const state = states[peer.node_id];
        return (
          <PeerCard 
            key={peer.node_id} 
            nodeId={peer.node_id} 
            port={peer.url.split(':').pop()} 
            alive={peer.alive} 
            state={state} 
            isTraceNode={traceNodeIds.has(peer.node_id)}
          />
        );
      })}
    </div>
  );
}

function PeerCard({ nodeId, port, alive, state, isTraceNode }) {
  if (!alive || !state) {
    return (
      <div className="bg-slate-50 border border-slate-200 p-4 rounded-lg flex flex-col items-center justify-center min-h-[300px]">
        <Server className="text-slate-300 mb-2" size={32} />
        <h3 className="text-lg font-bold text-slate-400">Node {nodeId}</h3>
        <span className="text-sm font-medium text-red-500 bg-red-50 px-2 py-0.5 rounded mt-2 border border-red-100">Offline</span>
      </div>
    );
  }

  return (
    <div className={`bg-white border-2 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col ${isTraceNode ? 'border-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.3)] ring-2 ring-amber-100' : 'border-slate-200'}`}>
      {/* Header */}
      <div className={`${isTraceNode ? 'bg-amber-50' : 'bg-slate-50'} border-b border-slate-200 p-3 flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${isTraceNode ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]' : 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]'} animate-pulse`}></div>
          <h3 className="font-bold text-slate-800 flex items-center gap-1.5">
            Node {nodeId}
            <span className="text-xs font-normal text-slate-500 bg-white px-1.5 rounded border border-slate-200">:{port}</span>
            {isTraceNode && <Activity size={14} className="text-amber-500 animate-bounce" />}
          </h3>
        </div>
        {!state.is_joined && (
          <span className="text-[10px] uppercase tracking-wider font-semibold bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded border border-yellow-200">Not Joined</span>
        )}
      </div>

      <div className="p-4 flex flex-col space-y-4 flex-grow">
        
        {/* Network & Routing */}
        <div>
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
            <Share2 size={12} /> Routing
          </h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
             <div className="bg-slate-50 rounded border border-slate-100 p-2">
                <span className="text-slate-500 block text-xs mb-0.5">Successor</span>
                <span className="font-mono font-medium text-slate-800">N{state.successor}</span>
             </div>
             <div className="bg-slate-50 rounded border border-slate-100 p-2">
                <span className="text-slate-500 block text-xs mb-0.5">Predecessor</span>
                <span className="font-mono font-medium text-slate-800">{state.predecessor !== null ? `N${state.predecessor}` : 'None'}</span>
             </div>
          </div>
        </div>

        {/* State Sections */}
        <div className="space-y-2">
           <ExpandableSection title="Finger Table" icon={<Hash size={12} />} count={state.finger_table.length}>
              <div className="max-h-48 overflow-y-auto pr-1 stylish-scrollbar">
                <table className="w-full text-xs text-left">
                  <thead className="sticky top-0 bg-white">
                    <tr className="text-slate-400">
                      <th className="pb-1 font-medium w-8">i</th>
                      <th className="pb-1 font-medium">start</th>
                      <th className="pb-1 font-medium">node</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-slate-600 divide-y divide-slate-50">
                    {state.finger_table.map((ft, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="py-1 text-slate-400">[{ft.index}]</td>
                        <td className="py-1">{ft.start}</td>
                        <td className="py-1 font-medium text-slate-800 md:text-blue-600">N{ft.node}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
           </ExpandableSection>

           <ExpandableSection title="DHT Store" icon={<Database size={12} />} count={Object.keys(state.dht_store).length} defaultOpen={true}>
              <StoreDisplay store={state.dht_store} />
           </ExpandableSection>

           <ExpandableSection title="Replica Store" icon={<HardDrive size={12} />} count={Object.keys(state.replica_store).length}>
              <StoreDisplay store={state.replica_store} />
           </ExpandableSection>
           
           <ExpandableSection title="Content Store" icon={<FileText size={12} />} count={Object.keys(state.content_store || {}).length}>
              <ContentDisplay store={state.content_store || {}} />
           </ExpandableSection>
           
           <ExpandableSection title="Replica Content" icon={<FileText size={12} />} count={Object.keys(state.replica_content_store || {}).length}>
              <ContentDisplay store={state.replica_content_store || {}} />
           </ExpandableSection>
        </div>
      </div>

      {/* Footer Stats & Actions */}
      <div className="bg-slate-50 border-t border-slate-200 p-3 flex flex-col gap-2 text-xs text-slate-500">
         <div className="flex items-center justify-between">
           <div className="flex items-center gap-1.5" title="Messages sent/received">
             <Activity size={12} /> {state.stats.message_count} msgs
           </div>
           <div className="flex gap-3">
             <span title="Keys in DHT">DHT: {state.stats.dht_key_count}</span>
             <span title="Content files">Doc: {state.stats.content_count || 0}</span>
           </div>
         </div>
         <div className="mt-1 flex justify-end">
            <button 
               onClick={async () => {
                  const title = prompt(`Enter title for new story to upload to Node ${nodeId}:`, "A P2P Story");
                  if (!title) return;
                  const content = prompt("Enter the content of the story:");
                  if (!content) return;
                  
                  const res = await api.uploadContent(nodeId, title, content);
                  if (res.error || res.data?.status === 'error') {
                     alert("Upload failed: " + (res.error || res.data?.detail));
                  } else {
                     alert(`Upload successful! New DocID generated: ${res.data.doc_id}`);
                  }
               }}
               className="flex items-center gap-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 px-2 py-1 rounded transition-colors font-semibold"
            >
               <Upload size={12} /> Upload Content
            </button>
         </div>
      </div>
    </div>
  );
}

function StoreDisplay({ store }) {
  const keys = Object.keys(store);
  if (keys.length === 0) return <div className="text-xs text-slate-400 py-1">Empty</div>;
  
  return (
    <div className="max-h-40 overflow-y-auto pr-1 stylish-scrollbar text-xs font-mono">
      <ul className="divide-y divide-slate-50">
        {keys.map(k => (
          <li key={k} className="py-1.5 flex align-top gap-2">
            <span className="text-indigo-600 font-semibold min-w-20 basis-1/3 break-all">"{k}"</span>
            <span className="text-slate-600 basis-2/3 break-words bg-slate-50 px-1 rounded">
              [{store[k].join(', ')}]
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContentDisplay({ store }) {
  const keys = Object.keys(store);
  if (keys.length === 0) return <div className="text-xs text-slate-400 py-1">Empty</div>;
  
  return (
    <div className="max-h-40 overflow-y-auto pr-1 stylish-scrollbar text-xs">
      <ul className="divide-y divide-slate-50">
        {keys.map(k => (
          <li key={k} className="py-1.5 flex flex-col gap-0.5">
            <span className="text-blue-600 font-mono font-semibold">DocID: {k}</span>
            <span className="text-slate-600 text-[11px] italic bg-slate-50 px-1.5 py-1 rounded">
              {store[k]}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExpandableSection({ title, icon, count, defaultOpen = false, children }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  return (
    <div className="border border-slate-200 rounded overflow-hidden">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-2 bg-slate-50 hover:bg-slate-100 transition-colors text-xs font-bold text-slate-600 uppercase tracking-wider"
      >
        <div className="flex items-center gap-1.5">
          {icon} {title}
          <span className="bg-white text-slate-400 border border-slate-200 px-1.5 py-0.5 rounded-full text-[10px] leading-none ml-1">
            {count}
          </span>
        </div>
        {isOpen ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400"/>}
      </button>
      {isOpen && (
        <div className="p-2 border-t border-slate-100 bg-white">
          {children}
        </div>
      )}
    </div>
  );
}
