"""
Demo Local — Full demo end-to-end chạy P2P Search trên LocalTransport.

Chạy: uv run python demo_local.py

Flow:
  1. Setup ring 5 nodes + publish index
  2. Query với trace readable  
  3. Churn simulation
  4. Xuất PNG visualizations
  5. In report cuối cùng
"""

import json
import os
import sys
import logging

# Set standard output and error to utf-8 to avoid UnicodeEncodeError on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from src.transport import LocalTransport
from src.chord.ring import ChordRing
from src.query_engine import QueryEngine
from src.metrics import MetricsCollector
from src.visualizer import NetworkVisualizer
from src.churn_simulation import ChurnSimulator


# ============================================================
# Config
# ============================================================

NODE_IDS = [10, 60, 110, 160, 210]
M = 8  # Chord address space: 2^8 = 256
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
GRAPHS_DIR = os.path.join(RESULTS_DIR, "graphs")
TRACES_DIR = os.path.join(RESULTS_DIR, "traces")

# Sample data — mô phỏng local index của mỗi peer
PEER_DATA = {
    10: {
        "system": [1, 2, 5],
        "database": [1, 2, 3],
        "network": [1, 5],
        "distributed": [2, 5],
    },
    60: {
        "system": [10, 12],
        "database": [10],
        "server": [10, 11],
    },
    110: {
        "network": [20, 21],
        "protocol": [20, 22],
        "distributed": [21],
    },
    160: {
        "database": [30, 31],
        "query": [30, 32],
        "search": [31, 32],
    },
    210: {
        "system": [40, 41],
        "search": [40, 42],
        "algorithm": [41, 42],
    },
}

TEST_QUERIES = [
    "system",
    "database",
    "system AND database",
    "network AND distributed",
    "search AND query",
    "nonexistent_keyword",
]


def ensure_dirs():
    """Tạo thư mục output."""
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    os.makedirs(TRACES_DIR, exist_ok=True)


def setup_network():
    """Khởi tạo mạng Chord + publish data."""
    logger.info("=" * 60)
    logger.info("PHASE 1: SETUP NETWORK")
    logger.info("=" * 60)
    
    transport = LocalTransport()
    ring = ChordRing.create(NODE_IDS, transport, m=M)
    
    logger.info(f"Ring created: {len(ring.nodes)} nodes, m={M}")
    logger.info(f"Node IDs: {sorted(ring.nodes.keys())}")
    
    # Verify topology
    for nid in sorted(ring.nodes.keys()):
        node = ring.nodes[nid]
        logger.info(f"  N{nid}: successor=N{node.successor_id}, predecessor=N{node.predecessor_id}")
    
    # Load local indexes + publish
    logger.info("\nPublishing local indexes to DHT...")
    for nid, index_data in PEER_DATA.items():
        node = ring.get_node(nid)
        if node:
            node.load_local_index(index_data)
            node.publish()
            logger.info(f"  N{nid}: published {len(index_data)} keywords")
    
    # Report DHT state
    logger.info("\nDHT State after publish:")
    for nid in sorted(ring.nodes.keys()):
        node = ring.nodes[nid]
        dht_keywords = list(node.dht_store.keys())
        replica_keywords = list(node.replica_store.keys())
        logger.info(f"  N{nid}: dht={dht_keywords}, replica={replica_keywords}")
    
    return transport, ring


def run_queries(ring, transport, queries, label=""):
    """Chạy queries và in trace readable."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 2: QUERIES {label}")
    logger.info(f"{'=' * 60}")
    
    qe = QueryEngine(ring)
    initiator_id = NODE_IDS[0]  # Node 10 là initiator
    
    results = []
    for q in queries:
        result = qe.query_and(initiator_id, q)
        results.append(result)
        
        # In trace readable
        trace_output = QueryEngine.format_query_trace(result)
        print(trace_output)
    
    return results


def run_metrics(transport, ring, query_results, label=""):
    """Thu thập và in metrics."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"METRICS {label}")
    logger.info(f"{'=' * 60}")
    
    mc = MetricsCollector(transport, ring)
    for qr in query_results:
        mc.add_query_result(qr)
    
    report = mc.generate_report()
    
    logger.info(f"  Total messages: {report.total_messages}")
    logger.info(f"  Messages by type: {report.messages_by_type}")
    logger.info(f"  Avg hops/query: {report.avg_hops_per_query:.2f}")
    logger.info(f"  DHT keys: {report.total_keys_in_dht}")
    logger.info(f"  Replication coverage: {report.replication_coverage:.1%}")
    logger.info(f"  Keys distribution: {report.keys_distribution}")
    
    # Node traffic
    logger.info("\n  Node Traffic:")
    for nt in report.node_traffic:
        logger.info(f"    N{nt.node_id}: sent={nt.sent}, received={nt.received}")
    
    return mc, report


def run_churn(ring, mc, node_to_remove):
    """Chạy churn simulation."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 3: CHURN SIMULATION — Remove N{node_to_remove}")
    logger.info(f"{'=' * 60}")
    
    simulator = ChurnSimulator(ring, mc)
    report = simulator.simulate(
        node_to_remove=node_to_remove,
        test_queries=TEST_QUERIES,
        stabilize_rounds=3,
    )
    
    print(report.format_readable())
    return report


def generate_visualizations(ring, query_results, churn_report=None):
    """Xuất PNG visualizations."""
    logger.info(f"\n{'=' * 60}")
    logger.info("PHASE 4: VISUALIZATIONS")
    logger.info(f"{'=' * 60}")
    
    try:
        viz = NetworkVisualizer(ring)
    except ImportError as e:
        logger.warning(f"  Skipping visualizer: {e}")
        return
        
    # Ring topology
    path = viz.draw_ring_topology(os.path.join(GRAPHS_DIR, "topology.png"))
    logger.info(f"  Ring topology: {path}")
    
    # DHT distribution
    path = viz.draw_dht_distribution(os.path.join(GRAPHS_DIR, "dht_distribution.png"))
    logger.info(f"  DHT distribution: {path}")
    
    # Query paths
    for i, qr in enumerate(query_results[:3]):  # Top 3 queries
        safe_name = qr.query.replace(" ", "_").replace("\"", "")[:30]
        path = viz.draw_query_path(qr, os.path.join(GRAPHS_DIR, f"query_{safe_name}.png"))
        logger.info(f"  Query path [{qr.query}]: {path}")
    
    # Churn comparison
    if churn_report:
        path = viz.draw_churn_comparison(
            [churn_report.removed_node_id],
            os.path.join(GRAPHS_DIR, "churn_comparison.png")
        )
        logger.info(f"  Churn comparison: {path}")


def save_traces(query_results, filename="query_traces.json"):
    """Lưu traces ra JSON."""
    traces = [qr.to_dict() for qr in query_results]
    output_path = os.path.join(TRACES_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2, ensure_ascii=False)
    logger.info(f"  Traces saved: {output_path}")


def main():
    """Entry point."""
    ensure_dirs()
    
    # === SETUP ===
    transport, ring = setup_network()
    
    # === QUERIES ===
    query_results = run_queries(ring, transport, TEST_QUERIES, label="(BEFORE CHURN)")
    
    # === METRICS ===
    mc, report_before = run_metrics(transport, ring, query_results, label="(BEFORE CHURN)")
    
    # === SAVE TRACES ===
    save_traces(query_results, "traces_before_churn.json")
    
    # === CHURN ===
    churn_report = run_churn(ring, mc, node_to_remove=60)
    
    # === QUERIES AFTER CHURN ===
    query_results_after = run_queries(ring, transport, TEST_QUERIES, label="(AFTER CHURN)")
    save_traces(query_results_after, "traces_after_churn.json")
    
    # === VISUALIZATIONS ===
    generate_visualizations(ring, query_results_after, churn_report)
    
    # === FINAL SUMMARY ===
    logger.info(f"\n{'=' * 60}")
    logger.info("DONE — All outputs in results/")
    logger.info(f"{'=' * 60}")
    logger.info(f"  Graphs: {GRAPHS_DIR}")
    logger.info(f"  Traces: {TRACES_DIR}")


if __name__ == "__main__":
    main()
