"""
Dashboard Backend — FastAPI aggregator cho Web Dashboard.

Vai trò:
- Aggregator: poll N peer servers, merge state thành 1 view
- Proxy: forward queries/commands tới peers  
- Static: serve React build files (production)

Chạy:
  python dashboard_server.py --peers "10:8001,60:8002,110:8003,160:8004,210:8005"

Thiết kế chống "god service":
- Dashboard KHÔNG sở hữu ChordNode hay state nào
- Chỉ đọc state từ peers qua HTTP (observer pattern)
- Chỉ forward commands, không tự quyết định logic
- Timeout ngắn khi gọi peers → peer chết = skip, không block

Chống polling spam:
- /api/ring-state dùng since param cho messages
- Client-side polling interval tối thiểu 2s
- Dashboard cache last state, chỉ diff khi cần
"""

import argparse
import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Thêm project root vào sys.path để import được src.*
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dashboard")


# ============================================================
# Request Models
# ============================================================

class QueryRequest(BaseModel):
    query: str
    initiator_node_id: Optional[int] = None  # None = first available peer

class ChurnRemoveRequest(BaseModel):
    node_id: int

class StabilizeAllRequest(BaseModel):
    rounds: int = 1

class PublishAllRequest(BaseModel):
    data_file: Optional[str] = None  # path to JSON, None = use default

class UploadRequest(BaseModel):
    content: str
    title: Optional[str] = "Untitled Document"

class AddPeerRequest(BaseModel):
    node_id: int
    url: str


# ============================================================
# Peer HTTP Client — thin wrapper to avoid repeating error handling
# ============================================================

class PeerClient:
    """
    HTTP client cho 1 peer server.
    Xử lý timeout, connection errors thống nhất.
    """
    def __init__(self, node_id: int, url: str, timeout: float = 5.0):
        self.node_id = node_id
        self.url = url
        self.timeout = timeout
    
    def get(self, path: str) -> Optional[dict]:
        try:
            r = httpx.get(f"{self.url}{path}", timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"GET {self.url}{path} failed: {e}")
            return None
    
    def post(self, path: str, data: dict = None) -> Optional[dict]:
        try:
            r = httpx.post(f"{self.url}{path}", json=data or {}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"POST {self.url}{path} failed: {e}")
            return None
    
    @property
    def is_alive(self) -> bool:
        result = self.get("/health")
        return result is not None and result.get("status") == "ok"


# ============================================================
# App Factory
# ============================================================

def create_dashboard_app(
    peers_config: Dict[int, str],  # {node_id: url}
    data_file: str = None,
    static_dir: str = None,
) -> FastAPI:
    
    app = FastAPI(title="P2P Chord DHT Dashboard")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # State
    peers: Dict[int, PeerClient] = {
        nid: PeerClient(nid, url) for nid, url in peers_config.items()
    }
    app.state.peers = peers
    app.state.data_file = data_file
    # Track message log cursors per peer (chống polling spam)
    app.state.msg_cursors: Dict[int, int] = {nid: 0 for nid in peers}
    
    # ============================================================
    # Aggregation APIs
    # ============================================================
    
    @app.get("/api/peers")
    def list_peers():
        """Danh sách peers đã config + alive status."""
        result = []
        for nid, client in peers.items():
            health = client.get("/health")
            result.append({
                "node_id": nid,
                "url": client.url,
                "alive": health is not None,
                "health": health,
            })
        return {"peers": result}

    @app.post("/api/peers/add")
    def add_peer(req: AddPeerRequest):
        """Đăng ký thêm 1 peer mới vào Dashboard (chưa join ring)."""
        node_id = req.node_id
        url = req.url
        if node_id in peers:
            return {"status": "error", "detail": "Node ID already exists"}
            
        peers[node_id] = PeerClient(node_id, url)
        app.state.msg_cursors[node_id] = 0
        return {"status": "ok", "node_id": node_id}
    
    @app.get("/api/ring-state")
    def get_ring_state():
        """
        Aggregate /api/state từ TẤT CẢ peers → combined view.
        Peer chết → skip, trả partial data + warning.
        """
        states = {}
        warnings = []
        
        for nid, client in peers.items():
            state = client.get("/api/state")
            if state:
                states[nid] = state
            else:
                warnings.append(f"Node {nid} unreachable")
        
        return {
            "states": states,
            "alive_count": len(states),
            "total_count": len(peers),
            "warnings": warnings,
        }
    
    @app.get("/api/messages/all")
    def get_all_messages(since_global: int = 0, limit: int = 100):
        """
        Aggregate message logs từ tất cả peers.
        
        Chống polling spam:
        - Mỗi peer track cursor riêng (chỉ fetch log mới)
        - Client gửi since_global (tổng entries đã nhận) → skip nếu không có gì mới
        """
        all_entries = []
        
        for nid, client in peers.items():
            cursor = app.state.msg_cursors.get(nid, 0)
            data = client.get(f"/api/messages?since={cursor}&limit={limit}")
            if data and data.get("entries"):
                for entry in data["entries"]:
                    entry["_peer_source"] = nid  # tag peer gốc
                all_entries.extend(data["entries"])
                # Update cursor
                app.state.msg_cursors[nid] = cursor + len(data["entries"])
        
        # Sort by timestamp
        all_entries.sort(key=lambda e: e.get("timestamp", 0))
        
        return {
            "entries": all_entries[-limit:],  # Limit
            "total_new": len(all_entries),
            "cursors": dict(app.state.msg_cursors),
        }
    
    @app.get("/api/metrics")
    def get_metrics():
        """Aggregate metrics từ tất cả peers."""
        total_messages = 0
        total_dht_keys = 0
        total_replica_keys = 0
        peer_traffic = []
        
        for nid, client in peers.items():
            state = client.get("/api/state")
            if state:
                stats = state.get("stats", {})
                msg_count = stats.get("message_count", 0)
                total_messages += msg_count
                total_dht_keys += stats.get("dht_key_count", 0)
                total_replica_keys += stats.get("replica_key_count", 0)
                peer_traffic.append({
                    "node_id": nid,
                    "messages": msg_count,
                    "dht_keys": stats.get("dht_key_count", 0),
                    "replica_keys": stats.get("replica_key_count", 0),
                })
        
        return {
            "total_messages": total_messages,
            "total_dht_keys": total_dht_keys,
            "total_replica_keys": total_replica_keys,
            "peer_traffic": sorted(peer_traffic, key=lambda x: x["node_id"]),
        }
    
    # ============================================================
    # Setup / Orchestration APIs
    # ============================================================
    
    @app.post("/api/setup/register")
    def register_all_peers():
        """Gửi peer list tới TẤT CẢ peers để mỗi node biết nhau."""
        peer_map = {str(nid): client.url for nid, client in peers.items()}
        results = {}
        
        for nid, client in peers.items():
            result = client.post("/api/register-peers", {"peers": peer_map})
            results[nid] = result if result else {"status": "unreachable"}
        
        return {"results": results}
    
    @app.post("/api/setup/join")
    def join_all_peers():
        """
        Join tuần tự: peer đầu tiên bootstrap, còn lại join via peer đầu.
        Thứ tự quan trọng — đừng parallel.
        """
        sorted_peers = sorted(peers.keys())
        bootstrap_id = sorted_peers[0]
        results = {}
        
        # Bootstrap node đầu tiên
        client = peers[bootstrap_id]
        result = client.post("/api/join", {"known_node_id": None})
        results[bootstrap_id] = result if result else {"status": "unreachable"}
        
        # Các node tiếp theo join via bootstrap
        for nid in sorted_peers[1:]:
            client = peers[nid]
            result = client.post("/api/join", {"known_node_id": bootstrap_id})
            results[nid] = result if result else {"status": "unreachable"}
        
        return {"results": results, "bootstrap": bootstrap_id}
    
    @app.post("/api/setup/stabilize")
    def stabilize_all(req: StabilizeAllRequest):
        """Stabilize tất cả peers, chạy tuần tự tránh race condition."""
        results = {}
        for _ in range(req.rounds):
            for nid, client in peers.items():
                result = client.post("/api/stabilize", {"rounds": 1})
                results[nid] = result if result else {"status": "unreachable"}
            time.sleep(0.1)  # Tiny delay giữa rounds
        
        return {"results": results, "rounds": req.rounds}
    
    @app.post("/api/setup/publish")
    def publish_all(req: PublishAllRequest = None):
        """
        Đọc data file (đã build sẵn local indexes) → phân chia cho peers → publish.
        """
        file_path = (req and req.data_file) or app.state.data_file
        
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "detail": f"Data file not found: {file_path}"}
        
        # Load raw stories JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                all_stories = json.load(f)
        except Exception as e:
            return {"status": "error", "detail": f"Failed to load JSON: {e}"}
        
        if not all_stories or not isinstance(all_stories, list):
            return {"status": "error", "detail": "Empty or invalid story data"}
            
        sorted_peer_ids = sorted(peers.keys())
        results = {}
        
        num_peers = len(sorted_peer_ids)
        if num_peers == 0:
            return {"status": "error", "detail": "No peers connected"}
            
        # Chia đều mảng truyện cho các node (round robin / chunk)
        chunk_size = (len(all_stories) + num_peers - 1) // num_peers
        chunks = [all_stories[i : i + chunk_size] for i in range(0, len(all_stories), chunk_size)]
        
        for i, nid in enumerate(sorted_peer_ids):
            chunk = chunks[i] if i < len(chunks) else []
            client = peers[nid]
            result = client.post("/api/publish", {"stories": chunk})
            results[nid] = {
                "stories_assigned": len(chunk),
                "publish_result": result if result else {"status": "unreachable"},
            }
        
        return {
            "status": "ok", 
            "results": results,
        }
    
    @app.post("/api/upload/{node_id}")
    def upload_content(node_id: int, req: UploadRequest):
        """Upload a single story to a specific node with auto-generated ID."""
        import time
        if node_id not in peers:
            return {"status": "error", "detail": f"Node {node_id} not found"}
            
        client = peers[node_id]
        if not client.is_alive:
            return {"status": "error", "detail": f"Node {node_id} is offline"}
            
        # Strategy 2: Node ID + Timestamp
        new_doc_id = int(f"{node_id}{int(time.time())}")
        
        story_payload = {
            "id": new_doc_id,
            "title": req.title,
            "content": req.content,
            "category": "User Upload"
        }
        
        result = client.post("/api/publish", {"stories": [story_payload]})
        if not result:
            return {"status": "error", "detail": "Failed to contact node"}
            
        return {
            "status": "ok",
            "doc_id": new_doc_id,
            "publish_result": result
        }
    
    # ============================================================
    # Query API
    # ============================================================
    
    @app.post("/api/query")
    def run_query(req: QueryRequest):
        """Forward query tới 1 peer, return full result."""
        # Chọn initiator
        if req.initiator_node_id and req.initiator_node_id in peers:
            initiator_id = req.initiator_node_id
        else:
            # Chọn peer đầu tiên alive
            initiator_id = next(
                (nid for nid, c in peers.items() if c.is_alive),
                None
            )
        
        if not initiator_id:
            return {"status": "error", "detail": "No alive peers"}
        
        client = peers[initiator_id]
        result = client.post("/api/query", {"query": req.query})
        
        if not result:
            return {"status": "error", "detail": f"Peer {initiator_id} unreachable"}
        
        return result
    
    @app.get("/api/content/{doc_id}")
    def get_content_proxy(doc_id: int):
        """Proxy request lấy nội dung tới 1 peer alive."""
        initiator_id = next(
            (nid for nid, c in peers.items() if c.is_alive),
            None
        )
        if not initiator_id:
            return {"status": "error", "detail": "No alive peers"}
            
        client = peers[initiator_id]
        result = client.get(f"/api/content/{doc_id}")
        if not result:
            return {"status": "error", "detail": f"Peer {initiator_id} unreachable"}
            
        # Ensure hash_value is present even if peer is old
        if result and isinstance(result, dict) and "hash_value" not in result and "status" in result and result["status"] == "ok":
            try:
                from src.chord.utils import deterministic_hash
                result["hash_value"] = deterministic_hash(str(doc_id), 8)
            except Exception as e:
                logger.error(f"Failed to inject hash_value: {e}")
            
        return result
    
    # ============================================================
    # Churn APIs
    # ============================================================
    
    @app.post("/api/churn/remove")
    def remove_peer(req: ChurnRemoveRequest):
        """
        Mô phỏng churn: xóa 1 peer khỏi ring.
        
        Không thực sự kill process — chỉ thông báo các peers khác
        xóa node chết khỏi registry. Peer chết tự biết mình bị loại
        khi các peer khác không gọi nữa.
        """
        target_id = req.node_id
        if target_id not in peers:
            return {"status": "error", "detail": f"Node {target_id} not in config"}
        
        # Xóa khỏi dashboard tracking
        removed_client = peers.pop(target_id)
        if target_id in app.state.msg_cursors:
            del app.state.msg_cursors[target_id]
        
        # Thông báo peers còn lại: re-register KHÔNG bao gồm node chết
        peer_map = {str(nid): client.url for nid, client in peers.items()}
        notify_results = {}
        for nid, client in peers.items():
            result = client.post("/api/register-peers", {"peers": peer_map})
            notify_results[nid] = result if result else {"status": "unreachable"}
        
        return {
            "status": "ok",
            "removed": target_id,
            "remaining_peers": list(peers.keys()),
            "notify_results": notify_results,
        }
    
    @app.post("/api/churn/stabilize-all")
    def stabilize_after_churn():
        """Stabilize tất cả sau churn — nhiều rounds hơn bình thường."""
        results = {}
        for _ in range(8):  # m=8 rounds
            for nid, client in peers.items():
                result = client.post("/api/stabilize", {"rounds": 1})
                results[nid] = result if result else {"status": "unreachable"}
            time.sleep(0.1)
        
        return {"results": results, "rounds": 8}
    
    @app.get("/api/data-preview")
    def preview_data():
        """Preview data file (cho UI biết sẽ publish gì)."""
        file_path = app.state.data_file
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "detail": "No data file configured"}
        
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        
        return {
            "total_docs": len(docs),
            "sample": docs[:3] if docs else [],
            "file": file_path,
        }
    
    # ============================================================
    # Static files (React build) — production mode
    # ============================================================
    
    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    
    return app




# ============================================================
# CLI
# ============================================================

def parse_peers(peers_str: str) -> Dict[int, str]:
    """Parse "10:8001,60:8002,..." → {10: "http://127.0.0.1:8001", ...}"""
    result = {}
    for pair in peers_str.split(","):
        parts = pair.strip().split(":")
        if len(parts) == 2:
            node_id = int(parts[0])
            port = int(parts[1])
            result[node_id] = f"http://127.0.0.1:{port}"
    return result


def main():
    parser = argparse.ArgumentParser(description="P2P Chord DHT Dashboard")
    parser.add_argument("--peers", required=True, 
                        help='Peer config: "10:8001,60:8002,110:8003"')
    parser.add_argument("--port", type=int, default=9000,
                        help="Dashboard port (default: 9000)")
    parser.add_argument("--data-file", default=None,
                        help="Path to dataset JSON file")
    parser.add_argument("--static-dir", default=None,
                        help="Path to React build directory")
    args = parser.parse_args()
    
    peers_config = parse_peers(args.peers)
    logger.info(f"Dashboard starting with peers: {peers_config}")
    
    app = create_dashboard_app(
        peers_config=peers_config,
        data_file=args.data_file,
        static_dir=args.static_dir,
    )
    
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
