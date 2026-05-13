import React, { useState } from 'react';
import { Search, Play, ArrowRight, CheckCircle2, XCircle, FileText } from 'lucide-react';
import { api } from '../api';

export function QueryPanel({ peers, onTraceUpdate }) {
  const [query, setQuery] = useState('');
  const [initiator, setInitiator] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  
  // Modal State cho Content Fetching
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [fetchingDoc, setFetchingDoc] = useState(false);
  const [docContent, setDocContent] = useState(null);

  const handleDocClick = async (docId) => {
    setFetchingDoc(true);
    setSelectedDoc(docId);
    setDocContent(null);
    try {
      const res = await api.fetchContent(docId);
      if (res.data) {
        setDocContent(res.data);
        if (onTraceUpdate && res.data.trace?.path) {
          onTraceUpdate(res.data.trace.path);
        }
      } else {
        setDocContent({ error: res.error || "Unknown error" });
      }
    } catch (err) {
      setDocContent({ error: err.message });
    } finally {
      setFetchingDoc(false);
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    if (onTraceUpdate) onTraceUpdate(null); // Clear cũ
    try {
      const res = await api.queryNetwork(query, initiator ? parseInt(initiator) : null);
      if (res.data) {
        setResult(res.data);
        // Cập nhật trace lên App để Visualize
        if (onTraceUpdate && res.data.lookups) {
           // Lấy path từ lookup đầu tiên (hoặc tất cả các path gộp lại)
           const allPaths = res.data.lookups.flatMap(l => l.routing_trace?.path || []);
           onTraceUpdate(allPaths);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200 h-full flex flex-col">
      <h2 className="text-lg font-semibold mb-4 text-slate-800 flex items-center gap-2">
        <Search size={18} className="text-slate-500"/> Query Network
      </h2>
      
      <form onSubmit={handleQuery} className="flex gap-2 mb-4">
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "system AND database"'
          className="flex-grow border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <select 
          value={initiator}
          onChange={(e) => setInitiator(e.target.value)}
          className="w-32 border border-slate-300 rounded-md px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">Auto Peer</option>
          {peers.filter(p => p.alive).map(p => (
            <option key={p.node_id} value={p.node_id}>Node {p.node_id}</option>
          ))}
        </select>
        <button 
          type="submit"
          disabled={loading || !query.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1 disabled:opacity-50"
        >
          {loading ? <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></div> : <Play size={16} />}
          Run
        </button>
      </form>

      {/* Results Area */}
      <div className="flex-grow border border-slate-200 rounded-md bg-slate-50 overflow-hidden flex flex-col">
        {!result && !loading && (
          <div className="flex-grow flex items-center justify-center text-slate-400 text-sm p-4 text-center">
            Enter a query to see step-by-step DHT routing trace and results.
          </div>
        )}
        
        {loading && (
          <div className="flex-grow flex items-center justify-center text-slate-500 text-sm">
            <div className="flex flex-col items-center gap-2">
              <div className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
              Routing through DHT...
            </div>
          </div>
        )}

        {result && !loading && (
          <div className="flex-grow overflow-y-auto p-4 stylish-scrollbar text-sm">
            
            {result.status === 'error' ? (
              <div className="text-red-600 p-3 bg-red-50 border border-red-100 rounded">
                Error: {result.detail}
              </div>
            ) : (
              <>
                <div className="mb-4">
                  <div className="font-semibold text-slate-800 mb-1">Final Result</div>
                  <div className="p-3 bg-white border border-slate-200 rounded flex items-center gap-2">
                     {result.final_result && result.final_result.length > 0 ? (
                       <>
                         <CheckCircle2 size={16} className="text-green-500" />
                         <span className="font-mono text-slate-700 flex flex-wrap gap-1">
                           [
                           {result.final_result.map((docId, i) => (
                             <React.Fragment key={docId}>
                               <button 
                                 onClick={() => handleDocClick(docId)}
                                 className="text-blue-600 hover:text-blue-800 hover:underline hover:bg-blue-50 px-1 rounded transition-colors cursor-pointer"
                                 title="Click to fetch content from DHT"
                               >
                                 {docId}
                               </button>
                               {i < result.final_result.length - 1 ? ', ' : ''}
                             </React.Fragment>
                           ))}
                           ]
                         </span>
                         <span className="text-slate-400 text-xs ml-auto">({result.final_result.length} doc{result.final_result.length > 1 ? 's' : ''})</span>
                       </>
                     ) : (
                       <>
                         <XCircle size={16} className="text-red-400" />
                         <span className="text-slate-600">No matching documents found.</span>
                       </>
                     )}
                  </div>
                  <div className="mt-2 text-xs text-slate-500 flex gap-4">
                     <span>Initiator: <strong>N{result.initiator}</strong></span>
                     <span>Total Messages: <strong>{result.total_messages}</strong></span>
                  </div>
                </div>

                <div className="font-semibold text-slate-800 mb-2">Routing Traces</div>
                
                <div className="space-y-4">
                  {result.lookups && result.lookups.map((lookup, idx) => (
                     <div key={idx} className="bg-white border border-slate-200 rounded overflow-hidden">
                       <div className="bg-slate-100 p-2 border-b border-slate-200 flex justify-between items-center text-xs">
                          <span className="font-mono font-semibold text-indigo-700">"{lookup.keyword}" <span className="text-slate-400 font-normal ml-1">hash={lookup.hash_value}</span></span>
                          <span className="text-slate-500 bg-white px-1.5 rounded">{lookup.doc_ids.length > 0 ? `[${lookup.doc_ids.join(', ')}]` : 'Empty'}</span>
                       </div>
                       
                       <div className="p-3 bg-white">
                         {lookup.routing_trace && lookup.routing_trace.path ? (
                            <ul className="space-y-2">
                              {lookup.routing_trace.path.map((hop, hidx) => (
                                <li key={hidx} className="flex flex-col text-xs font-mono">
                                   <div className="flex items-center gap-2 mb-0.5">
                                      <span className="bg-slate-100 text-slate-600 px-1.5 rounded border border-slate-200">N{hop.node}</span>
                                      
                                      {hop.action === 'FORWARD' && <ArrowRight size={12} className="text-blue-400" />}
                                      {hop.action === 'RESOLVED' && <ArrowRight size={12} className="text-green-500" />}
                                      {hop.action === 'FAILED' && <ArrowRight size={12} className="text-red-500" />}
                                      
                                      <span className={`px-1.5 rounded border ${
                                        hop.action === 'FORWARD' ? 'bg-blue-50 text-blue-700 border-blue-100' :
                                        hop.action === 'RESOLVED' ? 'bg-green-50 text-green-700 border-green-100' :
                                        'bg-red-50 text-red-700 border-red-100'
                                      }`}>
                                        {hop.action}
                                      </span>
                                      
                                      {hop.next_node !== hop.node && (
                                        <span className="bg-slate-100 text-slate-600 px-1.5 rounded border border-slate-200">N{hop.next_node}</span>
                                      )}
                                   </div>
                                   <span className="text-slate-400 pl-1 border-l-2 border-slate-100 ml-3 py-0.5" style={{fontFamily: 'sans-serif'}}>{hop.reason}</span>
                                </li>
                              ))}
                            </ul>
                         ) : (
                           <div className="text-xs text-slate-400 italic">No valid trace. {lookup.error}</div>
                         )}
                       </div>
                     </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Document Content Modal */}
      {selectedDoc && (
        <div className="absolute inset-0 bg-black/20 flex justify-center items-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90%] flex flex-col overflow-hidden border border-slate-200">
            <div className="bg-slate-50 border-b border-slate-200 p-3 flex justify-between items-center">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <FileText size={16} className="text-indigo-600" />
                Document {selectedDoc} 
                <span className="text-slate-400 font-mono font-normal text-xs ml-2">
                  (hash={docContent?.hash_value || docContent?.trace?.key || '...'})
                </span>
              </h3>
              <button 
                onClick={() => setSelectedDoc(null)}
                className="text-slate-400 hover:text-slate-600 hover:bg-slate-200 p-1 rounded transition-colors"
              >
                <XCircle size={20} />
              </button>
            </div>
            
            <div className="p-4 overflow-y-auto stylish-scrollbar flex-grow bg-white">
              {fetchingDoc ? (
                <div className="flex flex-col items-center justify-center py-10 text-slate-500">
                  <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mb-4"></div>
                  Fetching full content from DHT...
                </div>
              ) : docContent?.error ? (
                <div className="text-red-500 bg-red-50 p-4 rounded border border-red-100">
                  Error fetching document: {docContent.error}
                </div>
              ) : docContent?.doc ? (
                <div>
                  <h1 className="text-xl font-bold mb-2 text-slate-800">{docContent.doc.title || "Untitled"}</h1>
                  {docContent.doc.category && (
                    <span className="inline-block bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded border border-indigo-100 mb-4 font-medium uppercase tracking-wider">
                      {docContent.doc.category}
                    </span>
                  )}
                  <div className="text-slate-700 leading-relaxed whitespace-pre-wrap font-serif">
                    {docContent.doc.content}
                  </div>
                  
                  {/* Routing Trace của việc lấy Content */}
                  <div className="mt-6 pt-4 border-t border-slate-100">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Retrieval Routing Trace</h4>
                    {docContent.trace && docContent.trace.path && (
                      <ul className="space-y-1 bg-slate-50 p-3 rounded border border-slate-100">
                        {docContent.trace.path.map((hop, hidx) => (
                          <li key={hidx} className="flex items-center text-xs font-mono text-slate-600 gap-2">
                            <span className="bg-white px-1 border border-slate-200 rounded">N{hop.node}</span>
                            <ArrowRight size={10} className="text-slate-400" />
                            <span className="text-[10px] text-slate-400">{hop.action}</span>
                            <ArrowRight size={10} className="text-slate-400" />
                            <span className="bg-white px-1 border border-slate-200 rounded text-indigo-600 font-semibold">N{hop.next_node}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-slate-400 italic">No content returned.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
