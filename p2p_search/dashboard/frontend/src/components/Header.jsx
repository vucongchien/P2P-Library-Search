// Header.jsx
import React from 'react';
import { Activity, RefreshCcw } from 'lucide-react';

export function Header({ isPolling, startPolling, stopPolling, ringStatus }) {
  return (
    <header className="mb-6 flex flex-col md:flex-row md:items-center justify-between border-b pb-4 border-slate-200 gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          P2P Chord DHT Dashboard
          <span className="text-sm font-normal text-slate-500 ml-2">(Network Demo)</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">Monitoring & orchestration for the distributed search engine</p>
      </div>
      
      <div className="flex items-center gap-3">
        {/* Status Badge */}
        <div className={`px-3 py-1.5 flex items-center gap-2 rounded-md text-sm font-medium border ${
          ringStatus === 'stable' ? 'bg-green-50 text-green-700 border-green-200' :
          ringStatus === 'loading' ? 'bg-yellow-50 text-yellow-700 border-yellow-200' :
          'bg-slate-50 text-slate-600 border-slate-200'
        }`}>
          <Activity size={16} className={ringStatus === 'loading' ? 'animate-pulse' : ''} />
          {ringStatus === 'stable' ? 'Ring Stable' :
           ringStatus === 'loading' ? 'Bootstrapping...' : 'Network Idle'}
        </div>

        {/* Polling Toggle */}
        <button
          onClick={isPolling ? stopPolling : startPolling}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            isPolling 
              ? 'bg-slate-900 text-white hover:bg-slate-800' 
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          <RefreshCcw size={14} className={isPolling ? 'animate-spin' : ''} />
          {isPolling ? 'Auto-refresh On' : 'Auto-refresh Off'}
        </button>
      </div>
    </header>
  );
}
