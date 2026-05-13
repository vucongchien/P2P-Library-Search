#!/usr/bin/env python3
"""
P2P Network Demo (Phase 4)
--------------------------
Runs the full P2P Network (HTTP):
1. Spawn 5 Peer Servers (FastAPI + uvicorn)
2. Spawn 1 Dashboard Server aggregator
3. Opens Dashboard UI (React) in browser
"""

import sys
import os
import subprocess
import time
import signal
import webbrowser
from pathlib import Path

# Force UTF-8 encoding for stdout internally inside the script if possible
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PEERS = {
    10: 8001,
    60: 8002,
    110: 8003,
    160: 8004,
    210: 8005
}
DASHBOARD_PORT = 9000
DATA_FILE = os.path.abspath("../p2p_library_100_stories.json")
STATIC_DIR = os.path.abspath("dashboard/frontend/dist")

processes = []

def cleanup():
    """Kill all subprocesses."""
    print("\n[+] Cleaning up and shutting down servers...")
    for p in processes:
        try:
            p.terminate()
        except:
            pass
    print("[+] Done. Bye!")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    print(f"{'='*60}")
    print(">>> P2P CHORD DHT - NETWORK DEMO")
    print(f"{'='*60}")
    
    # Check if dataset exists, if not generate dummy
    if not os.path.exists(DATA_FILE):
        print(f"[!] Warning: {DATA_FILE} not found. Fallback to empty context.")
    
    # 1. Spawn Peer Servers
    print("\n[+] Starting isolated Peer Servers...")
    for node_id, port in PEERS.items():
        cmd = [
            sys.executable, "peer_server.py",
            "--node-id", str(node_id),
            "--port", str(port),
            "--m", "8"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p)
        print(f"  -> Node {node_id} @ port {port}")
    
    # 2. Spawn Dashboard Server
    print("\n[+] Starting Dashboard Aggregator...")
    peers_str = ",".join([f"{n}:{p}" for n, p in PEERS.items()])
    
    cmd_dash = [
        sys.executable, "dashboard/backend/dashboard_server.py",
        "--peers", peers_str,
        "--port", str(DASHBOARD_PORT)
    ]
    
    if os.path.exists(DATA_FILE):
        cmd_dash.extend(["--data-file", DATA_FILE])
    
    # Static UI serve
    if os.path.isdir(STATIC_DIR):
        cmd_dash.extend(["--static-dir", STATIC_DIR])
    else:
        print("[!] Warning: React UI build not found in dashboard/frontend/dist.")
        
    p_dash = subprocess.Popen(cmd_dash)
    processes.append(p_dash)
    print(f"  -> Dashboard API running on port {DASHBOARD_PORT}")
    
    # 3. Wait for boot
    print("\n[+] Waiting for servers to boot (3s)...")
    time.sleep(3)
    
    # 4. Open URL
    dashboard_url = f"http://127.0.0.1:{DASHBOARD_PORT}/"
    print(f"\n[OK] READY! Opening browser at: {dashboard_url}")
    print(f"[!] Press Ctrl+C in this terminal to shutdown everything.")
    
    if os.path.isdir(STATIC_DIR):
        webbrowser.open(dashboard_url)
    
    try:
        # Keep alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
