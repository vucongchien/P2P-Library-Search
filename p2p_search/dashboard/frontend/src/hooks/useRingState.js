import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';

/**
 * Generic polling hook
 */
export function usePolling(callback, interval = 2000, isEnabled = true) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isEnabled) return;

    const tick = () => {
      savedCallback.current();
    };

    // First run immediately 
    tick();

    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [interval, isEnabled]);
}

/**
 * Custom hook to manage the full DHT ring state
 */
export function useRingState() {
  const [peers, setPeers] = useState([]);
  const [states, setStates] = useState({});
  const [metrics, setMetrics] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isPolling, setIsPolling] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Pagination cursor cho messages
  const globalMsgCursor = useRef(0);

  const fetchState = useCallback(async () => {
    // Fetch Peers
    const pRes = await api.getPeers();
    if (pRes.data) setPeers(pRes.data.peers);

    // Fetch Ring States
    const rRes = await api.getRingState();
    if (rRes.data) setStates(rRes.data.states);

    // Fetch Metrics
    const mRes = await api.getMetrics();
    if (mRes.data) setMetrics(mRes.data);

    // Fetch Messages incrementally 
    const msgRes = await api.getMessages(); // We'll let backend handle the cursors per node natively or just use backend's memory limits
    if (msgRes.data && msgRes.data.entries.length > 0) {
      setMessages(prev => {
        // limit to 500 locally
        const newMsg = [...prev, ...msgRes.data.entries];
        return newMsg.slice(-500); 
      });
    }

    setLastUpdated(new Date());
  }, []);

  usePolling(fetchState, 2000, isPolling);

  const startPolling = () => setIsPolling(true);
  const stopPolling = () => setIsPolling(false);

  return {
    peers,
    states,
    metrics,
    messages,
    lastUpdated,
    isPolling,
    startPolling,
    stopPolling,
    refreshNow: fetchState
  };
}
