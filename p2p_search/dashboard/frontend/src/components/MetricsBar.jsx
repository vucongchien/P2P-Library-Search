import React from 'react';
import { BarChart3, MessageSquare, Database, FileText } from 'lucide-react';

export function MetricsBar({ metrics, states }) {
  if (!metrics || !states) return null;

  // Derive extra stats from states
  const totalKeywords = Object.values(states).reduce(
    (sum, state) => sum + (state.stats?.local_keyword_count || 0), 0
  );
  
  const dhtKeys = metrics.total_dht_keys || 0;
  const repKeys = metrics.total_replica_keys || 0;

  return (
    <div className="bg-white border-t border-slate-200 mt-6 pt-4 pb-4 px-6 flex flex-wrap gap-x-12 gap-y-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] sticky bottom-0 z-10 w-full">
      <div className="flex items-center gap-3">
        <div className="bg-blue-100 p-2 rounded-lg text-blue-600">
          <MessageSquare size={20} />
        </div>
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Total Messages</p>
          <p className="text-xl font-bold text-slate-800">{metrics.total_messages}</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="bg-indigo-100 p-2 rounded-lg text-indigo-600">
          <Database size={20} />
        </div>
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">DHT Keys Formed</p>
          <p className="text-xl font-bold text-slate-800">
             {dhtKeys} <span className="text-sm font-normal text-slate-400">master</span> + {repKeys} <span className="text-sm font-normal text-slate-400">replica</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="bg-emerald-100 p-2 rounded-lg text-emerald-600">
          <FileText size={20} />
        </div>
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Total Local Keywords</p>
          <p className="text-xl font-bold text-slate-800">{totalKeywords}</p>
        </div>
      </div>
      
      <div className="flex-grow flex items-center justify-end gap-3 min-w-[200px]">
        {metrics.peer_traffic && metrics.peer_traffic.length > 0 && (
           <div className="w-full max-w-[300px]">
             <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider text-right mb-1">
               Traffic Distribution (Msgs)
             </p>
             <div className="flex h-3 border border-slate-200 rounded-full overflow-hidden w-full bg-slate-50">
               {metrics.peer_traffic.map((pt, i) => {
                 const pct = metrics.total_messages > 0 
                   ? (pt.messages / metrics.total_messages) * 100 
                   : 0;
                 const colors = ['bg-blue-500', 'bg-indigo-500', 'bg-violet-500', 'bg-purple-500', 'bg-fuchsia-500'];
                 return (
                   <div 
                     key={pt.node_id}
                     style={{ width: `${pct}%` }}
                     className={colors[i % colors.length]}
                     title={`Node ${pt.node_id}: ${pt.messages} msgs (${pct.toFixed(1)}%)`}
                   />
                 );
               })}
             </div>
           </div>
        )}
      </div>
    </div>
  );
}
