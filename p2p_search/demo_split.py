#!/usr/bin/env python3
"""
P2P Network Demo - Tách riêng Terminal
--------------------------------------
Khởi động P2P Network nhưng bật lên 6 cửa sổ CMD riêng biệt:
- 5 cửa sổ cho Peer Servers (dễ dõng debug traceback/log).
- 1 cửa sổ cho Dashboard Backend.

Chống hiện tượng deadlock ngầm của stdout Windows khi chạy Popen chung.
"""

import os
import sys
import time
import webbrowser
from pathlib import Path

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

def main():
    print("="*60)
    print(">>> P2P CHORD DHT - MULTI-WINDOW DEMO")
    print("="*60)
    print("[!] Hệ thống sẽ bật lên 6 cửa sổ màn hình đen độc lập.")
    print("[!] Hãy giữ nguyên cửa sổ này để xem hướng dẫn.")
    print("")

    # 1. Bật 5 Peer Terminals
    executable = sys.executable
    
    for node_id, port in PEERS.items():
        title = f"Peer Node {node_id}"
        # Start command prompt and run uvicorn with auto-stabilize enabled
        cmd = f'start "{title}" cmd /k "{executable} peer_server.py --node-id {node_id} --port {port} --m 8 --auto-stabilize"'
        os.system(cmd)
        print(f"  -> Đã mở CMD cho Node {node_id} @ port {port}")
    
    print("\n[+] Đợi 3 giây để các Peer khởi động...")
    time.sleep(3)

    # 2. Bật Dashboard Terminal
    peers_str = ",".join([f"{n}:{p}" for n, p in PEERS.items()])
    dash_cmd_parts = [
        f"{executable}",
        "dashboard/backend/dashboard_server.py",
        f"--peers {peers_str}",
        f"--port {DASHBOARD_PORT}"
    ]
    
    if os.path.exists(DATA_FILE):
        dash_cmd_parts.append(f'--data-file "{DATA_FILE}"')
    
    if os.path.isdir(STATIC_DIR):
        dash_cmd_parts.append(f'--static-dir "{STATIC_DIR}"')
    
    dash_cmd = " ".join(dash_cmd_parts)
    os.system(f'start "Dashboard Aggregator API" cmd /k "{dash_cmd}"')
    print(f"  -> Đã mở CMD cho Dashboard @ port {DASHBOARD_PORT}")
    
    # 3. Chờ thêm 2 giây và mở Browser
    time.sleep(2)
    dashboard_url = f"http://127.0.0.1:{DASHBOARD_PORT}/"
    print(f"\n[OK] Đã mở trình duyệt tại: {dashboard_url}")
    print("\n[!] LƯU Ý KHI MUỐN TẮT MẠNG:")
    print("    Phải bấm nút [X] thủ công để tắt từng cửa sổ màu đen.")
    
    if os.path.isdir(STATIC_DIR):
        webbrowser.open(dashboard_url)

if __name__ == "__main__":
    main()
