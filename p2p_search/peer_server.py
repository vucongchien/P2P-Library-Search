"""
Peer Server — FastAPI server cho mỗi Chord peer.

Mỗi instance = 1 peer độc lập trong mạng P2P.
Sở hữu: ChordNode + NetworkTransport + message_log

Chạy:
  python peer_server.py --node-id 10 --port 8001 --m 8
  python peer_server.py --node-id 60 --port 8002 --m 8

Endpoints:
  POST /message          — Chord protocol messages (peer↔peer)
  POST /api/register-peers — Nhận peer list → update transport registry
  POST /api/join         — Trigger node.join()
  POST /api/stabilize    — 1 round stabilize + fix_fingers
  POST /api/publish      — Load local index + publish to DHT
  POST /api/query        — Run get() for keywords, return full trace
  GET  /api/state        — Full state dump
  GET  /api/messages     — Message log
  GET  /health           — Liveness check
"""

import argparse
import sys
import os
import logging
import json
import asyncio

# UTF-8 cho Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

# Ensure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from src.network_transport import NetworkTransport
from src.chord.node import ChordNode
from src.models import Message, Response as ChordResponse
from src.chord.utils import deterministic_hash
from src.preprocessing import clean_text, tokenize

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("peer_server")


# ============================================================
# Pydantic Request Models
# ============================================================

class RegisterPeersRequest(BaseModel):
    """Danh sách peers{node_id: url}."""
    peers: Dict[int, str]  # {10: "http://127.0.0.1:8001", ...}

class JoinRequest(BaseModel):
    """Trigger join vào ring."""
    known_node_id: Optional[int] = None  # None = bootstrap (node đầu tiên)

class StabilizeRequest(BaseModel):
    """Trigger stabilize."""
    rounds: int = 1

class PublishRequest(BaseModel):
    """Data để publish vào DHT."""
    stories: List[Dict[str, Any]]  # List of raw story dicts: [{"id": 1, "title": "...", "category": "...", "content": "..."}, ...]

class QueryRequest(BaseModel):
    """Query keyword(s)."""
    query: str  # e.g. "system AND database"


# ============================================================
# App Factory
# ============================================================

def create_app(node_id: int, port: int, m: int = 8) -> FastAPI:
    """
    Factory tạo FastAPI app cho 1 peer.
    
    Mỗi app sở hữu:
    - NetworkTransport riêng (HTTP client)
    - ChordNode riêng (routing + storage)
    """
    app = FastAPI(
        title=f"Chord Peer N{node_id}",
        description=f"P2P Chord DHT Node {node_id} on port {port}",
    )
    
    # CORS — cho phép Dashboard frontend gọi
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # State — khởi tạo khi startup
    transport = NetworkTransport()
    node = ChordNode(node_id, transport, m)
    
    # Lưu vào app.state cho endpoints truy cập
    app.state.node = node
    app.state.transport = transport
    app.state.node_id = node_id
    app.state.port = port
    app.state.m = m
    app.state.is_joined = False  # track trạng thái join
    
    # ============================================================
    # Background Maintenance Task (Autonomous Self-Healing)
    # ============================================================
    
    def run_maintenance_sync(interval: int):
        """Vòng lặp chạy trong Thread riêng để không block Event Loop của FastAPI."""
        logger.info(f"N{node_id}: Starting autonomous maintenance thread (interval={interval}s)")
        while True:
            try:
                # Thực hiện bảo trì với timeout ngắn (ví dụ 1s) để thoát nhanh nếu node chết
                # Lưu ý: Chúng ta gọi trực tiếp các hàm sync của node
                node.stabilize()
                node.fix_fingers()
                node.check_predecessor()
                
                # Log trạng thái định kỳ để người dùng dễ theo dõi
                logger.info(f"N{node_id} STATE: Successor=N{node.successor_id}, Predecessor=N{node.predecessor_id if node.predecessor_id else 'None'}")
                
            except Exception as e:
                # logger.error(f"N{node_id}: Maintenance cycle error: {e}")
                pass
            
            import time
            time.sleep(interval)

    @app.on_event("startup")
    async def startup_event():
        if getattr(app.state, "auto_stabilize", False):
            interval = getattr(app.state, "stabilize_interval", 5)
            # Chạy vòng lặp bảo trì trong một Thread riêng biệt (Daemon)
            import threading
            thread = threading.Thread(target=run_maintenance_sync, args=(interval,), daemon=True)
            thread.start()
    
    # Self-register: node biết về chính nó
    transport.register(node_id, f"http://127.0.0.1:{port}")
    
    # ============================================================
    # Chord Protocol Endpoint (peer↔peer)
    # ============================================================
    
    @app.post("/message")
    def receive_message(msg: dict):
        """
        Nhận Chord message từ peer khác.
        Đây là endpoint duy nhất mà NetworkTransport.send() gọi tới.
        """
        try:
            message = Message.from_dict(msg)
            response = app.state.node.handle_message(message)
            return response.to_dict()
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return ChordResponse(
                success=False,
                error="INTERNAL_ERROR",
                data={"details": str(e)}
            ).to_dict()

    # ============================================================
    # Management API (Dashboard → Peer)
    # ============================================================
    
    @app.post("/api/register-peers")
    def register_peers(req: RegisterPeersRequest):
        """
        Nhận danh sách peers → cập nhật transport registry.
        Dashboard gọi endpoint này cho TẤT CẢ peers để mọi node biết nhau.
        """
        registered = []
        for nid, url in req.peers.items():
            nid_int = int(nid)
            if nid_int == app.state.node_id:
                continue  # Không tự register vào chính mình (đã có)
            app.state.transport.register(nid_int, url)
            registered.append(nid_int)
        
        logger.info(f"Registered {len(registered)} peers: {registered}")
        return {
            "status": "ok", 
            "registered": registered,
            "total_known_peers": len(app.state.transport.registry)
        }
    
    @app.post("/api/join")
    def join_ring(req: JoinRequest):
        """
        Trigger Chord join protocol.
        - known_node_id=None → bootstrap (node đầu tiên, tự join)
        - known_node_id=10  → join ring qua Node 10
        """
        if app.state.is_joined:
            return {"status": "already_joined", "node_id": app.state.node_id}
        
        try:
            app.state.node.join(req.known_node_id)
            app.state.is_joined = True
            logger.info(
                f"Joined ring via N{req.known_node_id}. "
                f"Successor: N{app.state.node.successor_id}"
            )
            return {
                "status": "ok",
                "node_id": app.state.node_id,
                "successor": app.state.node.successor_id,
                "via": req.known_node_id,
            }
        except Exception as e:
            logger.error(f"Join failed: {e}", exc_info=True)
            return {"status": "error", "detail": str(e)}
    
    @app.post("/api/stabilize")
    def stabilize(req: StabilizeRequest):
        """
        Trigger stabilize + fix_fingers + check_predecessor.
        Dashboard gọi cho TẤT CẢ peers, mỗi peer tự stabilize.
        """
        node = app.state.node
        for _ in range(req.rounds):
            node.stabilize()
            node.fix_fingers()
            node.check_predecessor()
        
        logger.info(
            f"Stabilized {req.rounds} rounds. "
            f"Succ: N{node.successor_id}, Pred: N{node.predecessor_id}"
        )
        return {
            "status": "ok",
            "rounds": req.rounds,
            "successor": node.successor_id,
            "predecessor": node.predecessor_id,
        }
    
    @app.post("/api/publish")
    def publish_data(req: PublishRequest):
        """
        Nhận Raw Stories -> Tiền xử lý (Tokenize) -> Publish vào DHT (cả Index và Content).
        """
        node = app.state.node
        published_keywords = set()
        published_docs = 0
        
        for story in req.stories:
            doc_id = story.get("id")
            title = story.get("title", "")
            content = story.get("content", "")
            
            if doc_id is None:
                continue
                
            # 1. Store full content
            node.put_content(doc_id, story)
            published_docs += 1
            
            # 2. Tokenize and index keywords
            cleaned_text = clean_text(title, content)
            tokens = set(tokenize(cleaned_text))
            
            for keyword in tokens:
                node.put(keyword, {doc_id})
                published_keywords.add(keyword)
        
        logger.info(f"Published {published_docs} stories, {len(published_keywords)} unique keywords to DHT")
        return {
            "status": "ok",
            "stories_published": published_docs,
            "keywords_published": list(published_keywords),
            "dht_store_size": len(node.dht_store),
            "content_store_size": len(node.content_store)
        }
        
    @app.get("/api/content/{doc_id}")
    def get_content(doc_id: int):
        """
        Lấy Full Content thông qua quy trình DHT 1 bước (chỉ để demo single get).
        """
        node = app.state.node
        res = node.get_content(doc_id)
        if res.success:
            return {"status": "ok", "doc": res.data.get("content", {}), "trace": res.data.get("routing_trace")}
        return {"status": "error", "message": res.error}
    
    @app.post("/api/query")
    def query_keyword(req: QueryRequest):
        """
        Chạy DHT lookup cho query.
        
        Flow:
        1. Parse query → keywords
        2. Cho mỗi keyword: node.get(keyword) qua Chord routing
        3. Intersect results
        4. Trả full trace
        """
        node = app.state.node
        keywords = [k.strip() for k in req.query.lower().split() if k.strip() != "and"]
        
        if not keywords:
            return {"status": "error", "detail": "Empty query"}
        
        # Log start position cho message count
        start_log_idx = len(app.state.transport.message_log)
        
        lookups = []
        final_doc_ids = None
        
        for kw in keywords:
            response = node.get(kw)
            
            trace_dict = response.data.get("routing_trace", {}) if response.data else {}
            doc_ids = set(response.data.get("doc_ids", [])) if response.success else set()
            
            lookup_info = {
                "keyword": kw,
                "hash_value": deterministic_hash(kw, node.m),
                "success": response.success,
                "doc_ids": sorted(doc_ids),
                "routing_trace": trace_dict,
                "error": response.error,
            }
            lookups.append(lookup_info)
            
            # Incremental intersect
            if final_doc_ids is None:
                final_doc_ids = doc_ids
            else:
                final_doc_ids = final_doc_ids.intersection(doc_ids)
            
            # Early stop
            if not final_doc_ids:
                break
        
        total_messages = len(app.state.transport.message_log) - start_log_idx
        
        return {
            "status": "ok",
            "query": req.query,
            "keywords": keywords,
            "initiator": node.node_id,
            "lookups": lookups,
            "final_result": sorted(final_doc_ids) if final_doc_ids else [],
            "total_messages": total_messages,
        }

    @app.get("/api/content/{doc_id}")
    def get_document(doc_id: int):
        """Lấy nội dung truyện từ DHT qua Doc ID."""
        response = node.get_content(doc_id)
        if response.success:
            return {
                "status": "ok",
                "doc_id": doc_id,
                "hash_value": deterministic_hash(str(doc_id), node.m),
                "doc": response.data.get("content"), # {title, content, category}
                "trace": response.data.get("routing_trace")
            }
        else:
            return {
                "status": "error",
                "doc_id": doc_id,
                "hash_value": deterministic_hash(str(doc_id), node.m),
                "error": str(response.error),
                "trace": response.data.get("routing_trace")
            }

    # ============================================================
    # State / Observability API (Dashboard polling)
    # ============================================================
    
    @app.get("/api/state")
    def get_state():
        """
        Full state dump — Dashboard polls endpoint này.
        Hiển thị MỌI THỨ peer đang giữ.
        """
        node = app.state.node
        
        # Finger table với start positions
        finger_table = []
        for i in range(node.m):
            start = (node.node_id + (2 ** i)) % (2 ** node.m)
            finger_node = node.finger_table[i]
            finger_table.append({
                "index": i,
                "start": start,
                "node": finger_node,
            })
        
        # Convert sets → sorted lists cho JSON serialization
        dht_store = {k: sorted(v) for k, v in node.dht_store.items()}
        replica_store = {k: sorted(v) for k, v in node.replica_store.items()}
        local_index = {k: sorted(v) for k, v in node.local_index.items()} if hasattr(node, 'local_index') else {}
        
        # Build snippets for content store to display in UI
        def _build_content_snippets(store: dict) -> dict:
            snippets = {}
            for doc_id, doc in store.items():
                title = doc.get("title", f"Doc {doc_id}")
                content_preview = doc.get("content", "")[:40].replace("\n", " ")
                snippets[str(doc_id)] = f"{title} | {content_preview}..."
            return snippets
            
        content_store_snippets = _build_content_snippets(node.content_store)
        replica_content_snippets = _build_content_snippets(node.replica_content_store)
        
        return {
            "node_id": node.node_id,
            "port": app.state.port,
            "m": node.m,
            "is_joined": app.state.is_joined,
            "successor": node.successor_id,
            "successor_list": getattr(node, "successor_list", []),
            "predecessor": node.predecessor_id,
            "finger_table": finger_table,
            "dht_store": dht_store,
            "replica_store": replica_store,
            "local_index": local_index,
            "content_store": content_store_snippets,
            "replica_content_store": replica_content_snippets,
            "stats": {
                "dht_key_count": len(node.dht_store),
                "replica_key_count": len(node.replica_store),
                "local_keyword_count": len(local_index),
                "total_dht_docs": sum(len(v) for v in node.dht_store.values()),
                "total_replica_docs": sum(len(v) for v in node.replica_store.values()),
                "content_count": len(node.content_store),
                "replica_content_count": len(node.replica_content_store),
                "message_count": len(app.state.transport.message_log),
            },
            "known_peers": list(app.state.transport.registry.keys()),
            "status": "ok",
        }
    
    @app.get("/api/messages")
    def get_messages(since: int = 0, limit: int = 200):
        """
        Message log — phục vụ LogPanel trên Dashboard.
        
        Params:
        - since: index bắt đầu (tránh fetch lại log cũ → chống polling spam)
        - limit: max entries trả về
        """
        log = app.state.transport.message_log
        
        # Slice từ `since` index
        entries = log[since:since + limit]
        
        # Serialize — bỏ Message object, chỉ giữ metadata
        serialized = []
        for entry in entries:
            serialized.append({
                "from": entry["from"],
                "to": entry["to"],
                "type": entry["type"],
                "timestamp": entry["timestamp"],
                # payload summary (tránh payload quá lớn)
                "payload_keys": list(entry["message"].payload.keys()) if entry["message"].payload else [],
            })
        
        return {
            "entries": serialized,
            "total": len(log),
            "since": since,
            "has_more": since + limit < len(log),
        }
    
    @app.get("/health")
    def health():
        """Quick liveness check."""
        return {
            "node_id": app.state.node_id,
            "port": app.state.port,
            "is_joined": app.state.is_joined,
            "status": "ok",
        }
    
    return app


# ============================================================
# CLI Entry Point
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Chord Peer Server")
    parser.add_argument("--node-id", type=int, required=True, help="Node ID trong Chord ring")
    parser.add_argument("--port", type=int, required=True, help="HTTP port để lắng nghe")
    parser.add_argument("--m", type=int, default=8, help="Chord address space bits (default: 8)")
    parser.add_argument("--auto-stabilize", action="store_true", help="Bật chế độ tự động bảo trì mạng chạy ngầm")
    parser.add_argument("--stabilize-interval", type=int, default=5, help="Khoảng cách giữa các chu kỳ bảo trì (giây)")
    return parser.parse_args()


def main():
    args = parse_args()
    
    logger.info(f"Starting Chord Peer N{args.node_id} on port {args.port} (m={args.m})")
    
    app = create_app(node_id=args.node_id, port=args.port, m=args.m)
    
    # Lưu config vào app state để startup_event sử dụng
    app.state.auto_stabilize = args.auto_stabilize
    app.state.stabilize_interval = args.stabilize_interval
    
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        # Single worker — đảm bảo thread-safe cho ChordNode state
        workers=1,
    )


if __name__ == "__main__":
    main()
