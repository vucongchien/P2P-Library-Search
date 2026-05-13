import React, { useMemo } from 'react';

export function ChordRingViz({ states, activeTrace }) {
  const nodes = Object.values(states).filter(s => s.is_joined);
  
  // Calculate SVG dimensions
  const svgSize = 360;
  const center = svgSize / 2;
  const radius = 120; // Radius of the ring itself
  const maxNodeVal = 256; // Assuming m=8 as default config

  // Map nodes to positions on the ring
  const nodePositions = useMemo(() => {
    if (nodes.length === 0) return {};
    
    // Sort nodes to visualize them in order around the ring
    const sorted = [...nodes].sort((a,b) => a.node_id - b.node_id);
    const pos = {};
    
    sorted.forEach((n) => {
      // position by their ID on the ring (0 to 255 maps to 0 to 2PI)
      const angle = (n.node_id / maxNodeVal) * 2 * Math.PI - Math.PI / 2;
      pos[n.node_id] = {
        x: center + radius * Math.cos(angle),
        y: center + radius * Math.sin(angle),
        angle: angle
      };
    });
    return pos;
  }, [nodes]);

  // Extract nodes involved in the current active trace
  const traceHops = useMemo(() => {
    if (!activeTrace || activeTrace.length === 0) return [];
    return activeTrace;
  }, [activeTrace]);

  const traceNodeIds = useMemo(() => {
    const ids = new Set();
    traceHops.forEach(hop => {
      ids.add(hop.node);
      if (hop.next_node) ids.add(hop.next_node);
    });
    return ids;
  }, [traceHops]);

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400">
        <svg className="w-32 h-32 mb-4 text-slate-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p>No joined nodes to visualize</p>
      </div>
    );
  }

  // Draw arrow head marker
  const ArrowMarker = () => (
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
      </marker>
      <marker id="arrow-trace" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
      </marker>
      <marker id="arrow-self" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
      </marker>
      
      {/* Glow effect for trace */}
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="3" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
    </defs>
  );

  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-[360px] bg-white rounded-lg relative">
      <svg width="100%" height="100%" viewBox={`0 0 ${svgSize} ${svgSize}`} className="max-w-[400px]">
        <ArrowMarker />
        
        {/* Draw background ring */}
        <circle cx={center} cy={center} r={radius} fill="none" stroke="#f1f5f9" strokeWidth="30" />
        <circle cx={center} cy={center} r={radius} fill="none" stroke="#e2e8f0" strokeWidth="2" strokeDasharray="4 4" />
        
        {/* Draw edges (Successor links) */}
        {nodes.map(n => {
          if (!n.successor) return null;
          const start = nodePositions[n.node_id];
          const end = nodePositions[n.successor];
          
          if (!start || !end) return null;
          
          // Self-loop
          if (n.node_id === n.successor) {
            const loopRadius = 15;
            const lx = start.x + loopRadius * 1.5 * Math.cos(start.angle);
            const ly = start.y + loopRadius * 1.5 * Math.sin(start.angle);
            return (
              <circle 
                key={`edge-${n.node_id}-self`}
                cx={lx} cy={ly} r={loopRadius} 
                fill="none" stroke="#3b82f6" strokeWidth="2"
                markerEnd="url(#arrow-self)"
                strokeDasharray="2 2"
              />
            );
          }
          
          return (
            <path 
              key={`edge-${n.node_id}-${n.successor}`}
              d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
              stroke="#3b82f6" 
              strokeWidth="1.5" 
              fill="none"
              markerEnd="url(#arrow)"
              className="opacity-20"
            />
          );
        })}

        {/* Draw Active Trace Paths (Animated) */}
        {traceHops.map((hop, idx) => {
          const start = nodePositions[hop.node];
          const end = nodePositions[hop.next_node];
          if (!start || !end || hop.node === hop.next_node) return null;

          return (
            <g key={`trace-${idx}`}>
              <path 
                d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
                stroke="#f59e0b" 
                strokeWidth="4" 
                fill="none"
                markerEnd="url(#arrow-trace)"
                className="opacity-80"
                filter="url(#glow)"
              />
              <circle r="4" fill="#f59e0b">
                <animateMotion 
                  path={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
                  dur="0.8s" 
                  repeatCount="indefinite" 
                />
              </circle>
            </g>
          );
        })}

        {/* Draw Nodes */}
        {nodes.map(n => {
          const pos = nodePositions[n.node_id];
          if (!pos) return null;
          
          const isTraceNode = traceNodeIds.has(n.node_id);
          const dhtCount = Object.keys(n.dht_store || {}).length;
          
          return (
            <g key={`node-${n.node_id}`} className="cursor-pointer group">
              {/* Outer halo (active if trace node) */}
              <circle 
                cx={pos.x} cy={pos.y} r={isTraceNode ? "24" : "22"} 
                fill={isTraceNode ? "#fef3c7" : "#eff6ff"} 
                className={isTraceNode ? "opacity-100 animate-pulse" : "opacity-0 group-hover:opacity-100 transition-opacity"} 
              />
              
              {/* Node circle */}
              <circle 
                cx={pos.x} cy={pos.y} r="16" 
                fill="#ffffff" 
                stroke={isTraceNode ? "#f59e0b" : "#2563eb"} 
                strokeWidth={isTraceNode ? "4" : "2.5"} 
                className="shadow-sm transition-transform group-hover:scale-110"
              />
              
              {/* Node ID label */}
              <text 
                x={pos.x} y={pos.y} 
                textAnchor="middle" 
                dominantBaseline="central" 
                className={`text-[11px] font-bold pointer-events-none ${isTraceNode ? 'fill-amber-700' : 'fill-blue-700'}`}
              >
                N{n.node_id}
              </text>
              
              {/* Hash space tick marks */}
              <line x1={pos.x + 16 * Math.cos(pos.angle)} y1={pos.y + 16 * Math.sin(pos.angle)} 
                    x2={pos.x + 22 * Math.cos(pos.angle)} y2={pos.y + 22 * Math.sin(pos.angle)} 
                    stroke={isTraceNode ? "#f59e0b" : "#94a3b8"} strokeWidth="2" />
                    
              {/* Data indicator badge */}
              {dhtCount > 0 && (
                <circle cx={pos.x + 10} cy={pos.y - 10} r="6" fill="#8b5cf6" stroke="#fff" strokeWidth="2" />
              )}
            </g>
          );
        })}
        
        {/* Center label */}
        <text x={center} y={center} textAnchor="middle" dominantBaseline="central" className="text-sm font-semibold fill-slate-300 pointer-events-none">
          Chord DHT
        </text>
      </svg>
      
      {activeTrace && (
        <div className="absolute bottom-2 left-2 right-2 bg-amber-50 border border-amber-200 rounded p-2 text-[10px] text-amber-800 animate-in fade-in slide-in-from-bottom-2">
          <b>Query Route:</b> {activeTrace.map((h, i) => <span key={i}>N{h.node} {i < activeTrace.length - 1 ? '→ ' : ''}</span>)}
          {activeTrace.length > 0 && <span> → N{activeTrace[activeTrace.length-1].next_node} (Resolved)</span>}
        </div>
      )}

      <div className="mt-4 flex flex-wrap justify-center gap-4 text-[10px] text-slate-500">
        <div className="flex items-center gap-1"><div className="w-3 h-0.5 bg-blue-500 opacity-20"></div> Successor</div>
        <div className="flex items-center gap-1"><div className="w-3 h-0.5 bg-amber-500"></div> Routing Trace</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-violet-500"></div> Has Data</div>
      </div>
    </div>
  );
}
