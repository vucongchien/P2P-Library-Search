"""
Module Visualizer: Vẽ biểu đồ Chord ring topology bằng NetworkX + matplotlib.

Chức năng:
  - Vẽ ring topology: nodes + successor edges + finger table shortcuts
  - Highlight đường đi query (mỗi keyword 1 màu)
  - Bar chart phân bổ keys trên DHT
  - So sánh trước/sau churn

Output: PNG files lưu vào thư mục chỉ định.
"""

import math
import os
from typing import List, Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend cho server/CI
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    logger.warning("networkx/matplotlib chưa cài. Visualizer sẽ không hoạt động.")


# Bảng màu curated cho query paths
QUERY_COLORS = [
    "#FF6B6B",  # coral red
    "#4ECDC4",  # teal
    "#FFE66D",  # yellow
    "#A29BFE",  # lavender
    "#FD79A8",  # pink
    "#00CEC9",  # cyan
    "#6C5CE7",  # purple
    "#E17055",  # orange
]

# Màu nền và style
RING_EDGE_COLOR = "#2ECC71"       # successor ring — xanh lá
FINGER_EDGE_COLOR = "#BDC3C7"     # finger shortcuts — xám nhạt
NODE_COLOR = "#3498DB"            # node mặc định — xanh dương
INITIATOR_COLOR = "#E74C3C"       # node khởi tạo query — đỏ
TARGET_COLOR = "#F39C12"          # node đích (responsible) — vàng cam
BG_COLOR = "#2C3E50"              # nền tối
TEXT_COLOR = "#ECF0F1"            # chữ sáng


def _ensure_deps():
    """Kiểm tra dependencies trước khi vẽ."""
    if not HAS_DEPS:
        raise ImportError(
            "Cần cài networkx và matplotlib: uv add networkx matplotlib"
        )


class NetworkVisualizer:
    """
    Vẽ biểu đồ Chord ring topology.

    Chỉ ĐỌC trạng thái ring, không sửa gì.
    """

    def __init__(self, ring):
        """
        Args:
            ring: ChordRing instance (đọc .nodes, .m, .transport)
        """
        _ensure_deps()
        self.ring = ring
        self.m = ring.m

    # ----------------------------------------------------------
    # Private: Build graph data
    # ----------------------------------------------------------

    def _build_ring_graph(self) -> Tuple[Any, Dict[int, Tuple[float, float]]]:
        """Tạo NetworkX DiGraph từ ChordRing + circular layout."""
        G = nx.DiGraph()
        
        sorted_ids = sorted(self.ring.nodes.keys())
        n = len(sorted_ids)
        if n == 0:
            return G, {}

        # Circular layout: đặt nodes trên vòng tròn theo đúng vị trí ID trên không gian 2^m
        max_id = 2 ** self.m
        pos = {}
        for nid in sorted_ids:
            angle = 2 * math.pi * nid / max_id - math.pi / 2  # bắt đầu từ trên cùng
            x = math.cos(angle)
            y = math.sin(angle)
            pos[nid] = (x, y)

        # Thêm nodes
        for nid in sorted_ids:
            node = self.ring.nodes[nid]
            dht_keys = len(node.dht_store)
            replica_keys = len(getattr(node, "replica_store", {}))
            G.add_node(nid, dht_keys=dht_keys, replica_keys=replica_keys)

        # Thêm successor edges (ring chính)
        for nid in sorted_ids:
            node = self.ring.nodes[nid]
            if node.successor_id != nid and node.successor_id in self.ring.nodes:
                G.add_edge(nid, node.successor_id, edge_type="successor")

        # Thêm finger table edges (shortcuts)
        for nid in sorted_ids:
            node = self.ring.nodes[nid]
            for finger_id in node.finger_table:
                if (finger_id is not None
                        and finger_id != nid
                        and finger_id != node.successor_id
                        and finger_id in self.ring.nodes):
                    if not G.has_edge(nid, finger_id):
                        G.add_edge(nid, finger_id, edge_type="finger")

        return G, pos

    def _get_node_label(self, node_id: int) -> str:
        """Tạo label cho node: ID + metadata."""
        node = self.ring.nodes.get(node_id)
        if node is None:
            return str(node_id)
        dht_keys = len(node.dht_store)
        return f"Node {node_id}\n({dht_keys} keys)"

    # ----------------------------------------------------------
    # Public: Drawing methods
    # ----------------------------------------------------------

    def draw_ring_topology(self, save_path: str, title: str = "Chord Ring Topology",
                           show_fingers: bool = True, figsize: Tuple[int, int] = (12, 12)) -> str:
        """
        Vẽ ring topology cơ bản.

        Args:
            save_path: Đường dẫn file PNG output
            title: Tiêu đề biểu đồ
            show_fingers: Có vẽ finger table edges không
            figsize: Kích thước hình

        Returns:
            Đường dẫn file đã lưu
        """
        G, pos = self._build_ring_graph()
        if not G.nodes:
            logger.warning("Ring rỗng, không có gì để vẽ.")
            return save_path

        fig, ax = plt.subplots(1, 1, figsize=figsize, facecolor=BG_COLOR)
        ax.set_facecolor(BG_COLOR)
        ax.set_title(title, color=TEXT_COLOR, fontsize=16, fontweight="bold", pad=20)

        # Vẽ successor edges (vòng chính)
        successor_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "successor"]
        nx.draw_networkx_edges(
            G, pos, edgelist=successor_edges, ax=ax,
            edge_color=RING_EDGE_COLOR, width=2.5, alpha=0.9,
            arrows=True, arrowsize=20, arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )

        # Vẽ finger table edges (shortcuts)
        if show_fingers:
            finger_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "finger"]
            nx.draw_networkx_edges(
                G, pos, edgelist=finger_edges, ax=ax,
                edge_color=FINGER_EDGE_COLOR, width=1.0, alpha=0.3,
                arrows=True, arrowsize=12, arrowstyle="-|>",
                style="dashed",
                connectionstyle="arc3,rad=0.15",
            )

        # Vẽ nodes
        node_sizes = []
        for nid in G.nodes:
            dht_keys = G.nodes[nid].get("dht_keys", 0)
            node_sizes.append(800 + dht_keys * 50)  # Scale theo số keys

        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            node_color=NODE_COLOR, node_size=node_sizes,
            edgecolors=TEXT_COLOR, linewidths=2, alpha=0.9,
        )

        # Labels
        labels = {nid: self._get_node_label(nid) for nid in G.nodes}
        nx.draw_networkx_labels(
            G, pos, labels=labels, ax=ax,
            font_size=9, font_color=TEXT_COLOR, font_weight="bold",
        )

        # Legend
        legend_elements = [
            mpatches.Patch(color=RING_EDGE_COLOR, label="Successor ring"),
        ]
        if show_fingers:
            legend_elements.append(
                mpatches.Patch(color=FINGER_EDGE_COLOR, label="Finger shortcuts")
            )
        ax.legend(handles=legend_elements, loc="upper left",
                  facecolor=BG_COLOR, edgecolor=TEXT_COLOR, labelcolor=TEXT_COLOR)

        ax.axis("off")
        plt.tight_layout()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
        plt.close(fig)
        logger.info(f"Ring topology saved to {save_path}")
        return save_path

    def draw_query_path(self, query_result, save_path: str,
                        title: str = "Query Routing Path",
                        figsize: Tuple[int, int] = (14, 14)) -> str:
        """
        Vẽ ring topology + overlay đường đi routing của query.

        Mỗi keyword lookup → 1 màu khác nhau.
        Node initiator có viền đỏ, node đích có viền vàng.

        Args:
            query_result: QueryResult (có .trace chứa List[KeywordLookup])
            save_path: Đường dẫn file PNG
            title: Tiêu đề
            figsize: Kích thước

        Returns:
            Đường dẫn file đã lưu
        """
        G, pos = self._build_ring_graph()
        if not G.nodes:
            logger.warning("Ring rỗng, không vẽ query path.")
            return save_path

        fig, ax = plt.subplots(1, 1, figsize=figsize, facecolor=BG_COLOR)
        ax.set_facecolor(BG_COLOR)

        # Subtitle với thông tin query
        ax.set_title(
            f'{title}\nQuery: "{query_result.query}" | '
            f'Hops: {query_result.total_hops} | '
            f'Results: {len(query_result.final_result)}',
            color=TEXT_COLOR, fontsize=14, fontweight="bold", pad=20,
        )

        # Base: vẽ ring nhạt
        successor_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "successor"]
        nx.draw_networkx_edges(
            G, pos, edgelist=successor_edges, ax=ax,
            edge_color=RING_EDGE_COLOR, width=1.5, alpha=0.3,
            arrows=True, arrowsize=15, arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )

        # Xác định node đặc biệt
        initiator_id = query_result.initiator_peer
        target_ids = set()
        for lookup in query_result.trace:
            if lookup.responsible_peer is not None:
                target_ids.add(lookup.responsible_peer)

        # Vẽ nodes — phân loại màu
        regular_nodes = [n for n in G.nodes if n != initiator_id and n not in target_ids]
        
        if regular_nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=regular_nodes, ax=ax,
                node_color=NODE_COLOR, node_size=800,
                edgecolors=TEXT_COLOR, linewidths=2, alpha=0.6,
            )
        if initiator_id in G.nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=[initiator_id], ax=ax,
                node_color=INITIATOR_COLOR, node_size=1200,
                edgecolors="#FFFFFF", linewidths=3, alpha=0.95,
            )
        target_nodes_in_graph = [t for t in target_ids if t in G.nodes and t != initiator_id]
        if target_nodes_in_graph:
            nx.draw_networkx_nodes(
                G, pos, nodelist=target_nodes_in_graph, ax=ax,
                node_color=TARGET_COLOR, node_size=1000,
                edgecolors="#FFFFFF", linewidths=3, alpha=0.95,
            )

        # Labels
        labels = {nid: f"N{nid}" for nid in G.nodes}
        nx.draw_networkx_labels(
            G, pos, labels=labels, ax=ax,
            font_size=10, font_color=TEXT_COLOR, font_weight="bold",
        )

        # Overlay: query path cho mỗi keyword
        legend_elements = [
            mpatches.Patch(color=INITIATOR_COLOR, label=f"Initiator (N{initiator_id})"),
            mpatches.Patch(color=TARGET_COLOR, label="Responsible peer"),
        ]

        for idx, lookup in enumerate(query_result.trace):
            color = QUERY_COLORS[idx % len(QUERY_COLORS)]
            path_edges = []

            for hop in lookup.routing_path:
                from_node = hop.from_node
                to_node = hop.to_node
                # Chỉ vẽ nếu cả 2 node đều có trong pos
                if from_node in pos and to_node in pos:
                    path_edges.append((from_node, to_node))

            if path_edges:
                # Thêm edges vào graph nếu chưa có (để vẽ)
                temp_G = nx.DiGraph()
                temp_G.add_nodes_from(G.nodes)
                temp_G.add_edges_from(path_edges)

                nx.draw_networkx_edges(
                    temp_G, pos, edgelist=path_edges, ax=ax,
                    edge_color=color, width=3.0, alpha=0.85,
                    arrows=True, arrowsize=25, arrowstyle="-|>",
                    connectionstyle=f"arc3,rad={0.2 + idx * 0.05}",
                )

            legend_elements.append(
                mpatches.Patch(
                    color=color,
                    label=f'"{lookup.keyword}" → N{lookup.responsible_peer} ({lookup.hops} hops)',
                )
            )

        ax.legend(
            handles=legend_elements, loc="upper left",
            facecolor=BG_COLOR, edgecolor=TEXT_COLOR, labelcolor=TEXT_COLOR,
            fontsize=10,
        )

        ax.axis("off")
        plt.tight_layout()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
        plt.close(fig)
        logger.info(f"Query path saved to {save_path}")
        return save_path

    def draw_dht_distribution(self, save_path: str,
                              title: str = "DHT Key Distribution",
                              figsize: Tuple[int, int] = (12, 6)) -> str:
        """
        Vẽ bar chart phân bổ DHT keys trên các node.
        Stacked: dht_store (primary) vs replica_store (backup).

        Returns:
            Đường dẫn file đã lưu
        """
        sorted_ids = sorted(self.ring.nodes.keys())
        if not sorted_ids:
            logger.warning("Ring rỗng, không vẽ distribution.")
            return save_path

        dht_counts = []
        replica_counts = []
        labels = []

        for nid in sorted_ids:
            node = self.ring.nodes[nid]
            dht_counts.append(len(node.dht_store))
            replica_counts.append(len(getattr(node, "replica_store", {})))
            labels.append(f"N{nid}")

        fig, ax = plt.subplots(1, 1, figsize=figsize, facecolor=BG_COLOR)
        ax.set_facecolor(BG_COLOR)

        x = range(len(sorted_ids))
        bar_width = 0.6

        bars1 = ax.bar(x, dht_counts, bar_width, label="DHT Primary", color="#3498DB", alpha=0.9)
        bars2 = ax.bar(x, replica_counts, bar_width, bottom=dht_counts,
                       label="Replica", color="#E67E22", alpha=0.7)

        # Value labels trên mỗi bar
        for bar, count in zip(bars1, dht_counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                        str(count), ha="center", va="center",
                        color=TEXT_COLOR, fontweight="bold", fontsize=11)

        for bar, dht_c, rep_c in zip(bars2, dht_counts, replica_counts):
            if rep_c > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, dht_c + rep_c / 2,
                        str(rep_c), ha="center", va="center",
                        color=TEXT_COLOR, fontweight="bold", fontsize=11)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, color=TEXT_COLOR, fontsize=12)
        ax.set_ylabel("Number of Keys", color=TEXT_COLOR, fontsize=12)
        ax.set_title(title, color=TEXT_COLOR, fontsize=14, fontweight="bold")
        ax.tick_params(colors=TEXT_COLOR)
        ax.legend(facecolor=BG_COLOR, edgecolor=TEXT_COLOR, labelcolor=TEXT_COLOR)

        for spine in ax.spines.values():
            spine.set_color(TEXT_COLOR)

        plt.tight_layout()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
        plt.close(fig)
        logger.info(f"DHT distribution saved to {save_path}")
        return save_path

    def draw_churn_comparison(self, removed_node_ids: List[int], save_path: str,
                              title: str = "Network After Churn",
                              figsize: Tuple[int, int] = (12, 12)) -> str:
        """
        Vẽ ring sau churn với highlight node đã bị xóa.
        
        Args:
            removed_node_ids: Danh sách node đã bị remove
            save_path: Đường dẫn file PNG
            title: Tiêu đề
            figsize: Kích thước
            
        Returns:
            Đường dẫn file đã lưu
        """
        G, pos = self._build_ring_graph()

        # Thêm ghost nodes cho các node đã bị xóa (nếu biết vị trí)
        max_id = 2 ** self.m
        for dead_id in removed_node_ids:
            if dead_id not in G.nodes:
                angle = 2 * math.pi * dead_id / max_id - math.pi / 2
                pos[dead_id] = (math.cos(angle), math.sin(angle))
                G.add_node(dead_id, dht_keys=0, replica_keys=0, dead=True)

        fig, ax = plt.subplots(1, 1, figsize=figsize, facecolor=BG_COLOR)
        ax.set_facecolor(BG_COLOR)
        ax.set_title(
            f'{title}\nRemoved: {removed_node_ids}',
            color=TEXT_COLOR, fontsize=14, fontweight="bold", pad=20,
        )

        # Vẽ edges
        successor_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "successor"]
        nx.draw_networkx_edges(
            G, pos, edgelist=successor_edges, ax=ax,
            edge_color=RING_EDGE_COLOR, width=2.5, alpha=0.8,
            arrows=True, arrowsize=20, arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )

        # Phân loại nodes
        alive_nodes = [n for n in G.nodes if n not in removed_node_ids]
        dead_nodes = [n for n in G.nodes if n in removed_node_ids]

        if alive_nodes:
            sizes = [800 + G.nodes[n].get("dht_keys", 0) * 50 for n in alive_nodes]
            nx.draw_networkx_nodes(
                G, pos, nodelist=alive_nodes, ax=ax,
                node_color=NODE_COLOR, node_size=sizes,
                edgecolors=TEXT_COLOR, linewidths=2, alpha=0.9,
            )

        if dead_nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=dead_nodes, ax=ax,
                node_color="#E74C3C", node_size=800,
                edgecolors="#FF0000", linewidths=3, alpha=0.5,
                node_shape="X",
            )

        # Labels
        labels = {}
        for nid in alive_nodes:
            labels[nid] = self._get_node_label(nid)
        for nid in dead_nodes:
            labels[nid] = f"N{nid}\n(DEAD)"
        nx.draw_networkx_labels(
            G, pos, labels=labels, ax=ax,
            font_size=9, font_color=TEXT_COLOR, font_weight="bold",
        )

        # Legend
        legend_elements = [
            mpatches.Patch(color=NODE_COLOR, label="Alive nodes"),
            mpatches.Patch(color="#E74C3C", label="Removed nodes"),
            mpatches.Patch(color=RING_EDGE_COLOR, label="Successor ring"),
        ]
        ax.legend(handles=legend_elements, loc="upper left",
                  facecolor=BG_COLOR, edgecolor=TEXT_COLOR, labelcolor=TEXT_COLOR)

        ax.axis("off")
        plt.tight_layout()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
        plt.close(fig)
        logger.info(f"Churn comparison saved to {save_path}")
        return save_path
