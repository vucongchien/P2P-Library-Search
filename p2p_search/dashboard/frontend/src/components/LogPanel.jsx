import React, { useState, useEffect, useRef } from 'react';
import { AlignLeft, Download, Trash2, Filter } from 'lucide-react';

export function LogPanel({ messages }) {
  const [filterType, setFilterType] = useState('ALL');
  const [filterNode, setFilterNode] = useState('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  
  const endRef = useRef(null);

  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  const filteredLogs = messages.filter(msg => {
    if (filterType !== 'ALL' && msg.type !== filterType) return false;
    if (filterNode !== 'ALL') {
      const node = parseInt(filterNode);
      if (msg.from !== node && msg.to !== node) return false;
    }
    return true;
  });

  const exportLogs = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(messages, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute("href", dataStr);
    dlAnchorElem.setAttribute("download", "p2p_message_log.json");
    dlAnchorElem.click();
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200 h-full flex flex-col">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-2 border-b pb-2 border-slate-100">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <AlignLeft size={18} className="text-slate-500" /> Event Log
        </h2>
        
        <div className="flex items-center gap-2 text-xs">
          <Filter size={14} className="text-slate-400" />
          <select 
            value={filterType} 
            onChange={e => setFilterType(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1 bg-white"
          >
            <option value="ALL">All Types</option>
            <option value="FIND_SUCCESSOR">FIND_SUCCESSOR</option>
            <option value="GET_PREDECESSOR">GET_PREDECESSOR</option>
            <option value="NOTIFY">NOTIFY</option>
            <option value="PUT">PUT</option>
            <option value="GET">GET</option>
            <option value="TRANSFER_KEYS">TRANSFER_KEYS</option>
            <option value="RESPONSE">RESPONSE</option>
          </select>
          
          <select 
            value={filterNode} 
            onChange={e => setFilterNode(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1 bg-white"
          >
            <option value="ALL">All Nodes</option>
            {/* Get unique nodes from messages */}
            {[...new Set(messages.flatMap(m => [m.from, m.to]))].sort((a,b)=>a-b).map(n => (
              <option key={n} value={n}>Node {n}</option>
            ))}
          </select>
          
          <button 
            onClick={exportLogs}
            title="Export JSON"
            className="p-1 text-slate-500 hover:text-blue-600 bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 rounded"
          >
            <Download size={16} />
          </button>
        </div>
      </div>
      
      <div className="flex-grow overflow-y-auto stylish-scrollbar bg-slate-900 rounded-md text-slate-300 font-mono text-xs p-3">
        {filteredLogs.length === 0 ? (
          <div className="text-slate-500 italic flex items-center justify-center h-full">
            No events logged yet matching current filters.
          </div>
        ) : (
          <ul className="space-y-1 pb-2">
            {filteredLogs.map((msg, idx) => (
              <li key={idx} className="flex align-top">
                <span className="text-slate-500 mr-3 min-w-[70px]">
                  {new Date(msg.timestamp * 1000).toISOString().split('T')[1].slice(0, 12)}
                </span>
                
                <span className="mr-3 min-w-[70px]">
                  <span className="text-blue-400">N{msg.from}</span>
                  <span className="text-slate-500 px-0.5">→</span>
                  <span className="text-emerald-400">N{msg.to}</span>
                </span>
                
                <span className={`mr-2 min-w-[125px] font-semibold ${
                  msg.type === 'RESPONSE' ? 'text-green-500' :
                  msg.type.includes('SUCCESSOR') ? 'text-indigo-400' : 
                  msg.type === 'PUT' || msg.type === 'GET' ? 'text-violet-400' :
                  'text-yellow-400'
                }`}>
                  {msg.type}
                </span>
                
                <span className="text-slate-400 truncate">
                   {msg.payload_keys && msg.payload_keys.length > 0 ? 
                     `{${msg.payload_keys.join(', ')}}` : ''}
                </span>
              </li>
            ))}
            <div ref={endRef} />
          </ul>
        )}
      </div>
      
      <div className="mt-2 text-xs flex justify-between items-center text-slate-500">
         <span>Showing {filteredLogs.length} of {messages.length} total messages</span>
         <label className="flex items-center gap-1.5 cursor-pointer">
           <input 
             type="checkbox" 
             checked={autoScroll} 
             onChange={e => setAutoScroll(e.target.checked)} 
             className="rounded border-slate-300"
           />
           Auto-scroll
         </label>
      </div>
    </div>
  );
}
