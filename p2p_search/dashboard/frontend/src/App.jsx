import React from 'react';
import { useRingState } from './hooks/useRingState';
import { Header } from './components/Header';
import { Controls } from './components/Controls';
import { ChordRingViz } from './components/ChordRingViz';
import { QueryPanel } from './components/QueryPanel';
import { LogPanel } from './components/LogPanel';
import { PeerList } from './components/PeerCard';
import { MetricsBar } from './components/MetricsBar';

function App() {
  const { 
    peers, 
    states, 
    metrics, 
    messages, 
    isPolling, 
    startPolling, 
    stopPolling,
    refreshNow 
  } = useRingState();
  
  const [activeTrace, setActiveTrace] = React.useState(null);

  // Calculate high-level ring status
  const aliveNodes = peers.filter(p => p.alive);
  const joinedNodes = Object.values(states).filter(s => s.is_joined);
  
  let ringStatus = 'idle';
  if (peers.length > 0) ringStatus = 'loading';
  if (aliveNodes.length > 0 && aliveNodes.length === joinedNodes.length && joinedNodes.every(n => n.successor !== null)) {
    ringStatus = 'stable';
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-4 relative pb-32">
      
      <Header 
        isPolling={isPolling} 
        startPolling={startPolling} 
        stopPolling={stopPolling} 
        ringStatus={ringStatus} 
      />
      
      <Controls 
        peers={peers} 
        refreshData={refreshNow} 
      />

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left Column: Visualization */}
        <div className="lg:col-span-1 border border-slate-200 bg-white rounded-lg p-2 shadow-sm flex flex-col h-[600px]">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2 pt-2">Topology</h2>
          <div className="flex-grow flex items-center justify-center relative">
            <ChordRingViz states={states} activeTrace={activeTrace} />
          </div>
        </div>
        
        {/* Right Column: Interaction & Logs */}
        <div className="lg:col-span-2 flex flex-col gap-6 h-[600px]">
          <div className="h-1/2 min-h-[250px]">
             <QueryPanel peers={peers} onTraceUpdate={setActiveTrace} />
          </div>
          
          <div className="h-1/2 min-h-[300px]">
             <LogPanel messages={messages} />
          </div>
        </div>
      </main>
      
      <div className="mb-12">
        <h2 className="text-lg font-semibold mb-4 text-slate-800 flex items-center gap-2">
          Active Peers
          <span className="text-xs font-normal bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full border border-blue-200">
             {aliveNodes.length} nodes
          </span>
        </h2>
        <PeerList peers={peers} states={states} activeTrace={activeTrace} refreshData={refreshNow} />
      </div>

      <MetricsBar metrics={metrics} states={states} />
    </div>
  );
}

export default App;
