"""
graph_builder.py — NetworkX Application Graph Builder + Analyzer
Builds full attack surface map; AI uses this to decide what to attack
MilkyWay Intelligence | Author: Sharlix
"""
import json
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False

NODE_PRIORITY = {
    "AUTH": 10, "PAYMENT": 9, "ADMIN": 8, "GRAPHQL": 8,
    "FILE": 7,  "PROFILE": 6, "API": 5,  "NORMAL": 3,
    "WEBSOCKET": 7
}


class GraphBuilder:
    def __init__(self, db, logger, out_dir: str, prefix: str):
        self.db      = db
        self.log     = logger
        self.out_dir = out_dir
        self.prefix  = prefix
        self.G       = nx.DiGraph() if NX_AVAILABLE else None

    def build(self) -> Dict:
        """Build full graph from DB nodes + edges."""
        nodes = self.db.get_all_nodes()
        if not nodes:
            self.log.warn("Graph: no nodes in DB")
            return {"nodes": 0, "edges": 0}

        if self.G is not None:
            self.G.clear()

        for node in nodes:
            self._add_node(node)

        # Add edges from DB
        rows = self.db.conn.execute(
            "SELECT * FROM edges"
        ).fetchall()
        for row in rows:
            self._add_edge(dict(row))

        # Infer edges from URL structure
        self._infer_edges(nodes)

        stats = {
            "nodes": len(nodes),
            "edges": len(rows),
        }
        self.log.success(
            f"Graph: {stats['nodes']} nodes, {stats['edges']} edges"
        )
        self._save(nodes, rows)
        return stats

    def get_attack_surface(self) -> Dict:
        """
        Return structured attack surface for AI context.
        Groups nodes by type, sorted by priority.
        """
        nodes = self.db.get_all_nodes()
        surface = {}
        for node in nodes:
            ntype = node.get("node_type", "NORMAL")
            if ntype not in surface:
                surface[ntype] = []
            surface[ntype].append({
                "url":      node["url"],
                "method":   node.get("method", '["GET"]'),
                "params":   node.get("params", "[]"),
                "tested":   bool(node.get("tested")),
                "priority": node.get("priority", 3)
            })

        # Sort each type by priority desc
        for ntype in surface:
            surface[ntype].sort(
                key=lambda x: x["priority"], reverse=True
            )
        return surface

    def find_attack_paths(self) -> List[Dict]:
        """
        Find paths from low-privilege nodes to high-privilege targets.
        Used by chain detector.
        """
        if not NX_AVAILABLE or not self.G:
            return []
        paths   = []
        targets = [n for n, d in self.G.nodes(data=True)
                   if d.get("node_type") in ("ADMIN", "PAYMENT")]
        sources = [n for n, d in self.G.nodes(data=True)
                   if d.get("node_type") in ("NORMAL", "API")]

        for src in sources[:5]:
            for tgt in targets[:5]:
                try:
                    if nx.has_path(self.G, src, tgt):
                        path = nx.shortest_path(self.G, src, tgt)
                        paths.append({
                            "from": src, "to": tgt,
                            "path": path, "length": len(path)
                        })
                except Exception:
                    pass
        return paths

    def get_untested_high_priority(self, limit: int = 10) -> List[Dict]:
        """Returns untested nodes sorted by priority."""
        nodes = self.db.get_untested_nodes(limit=limit)
        return sorted(nodes,
                      key=lambda n: NODE_PRIORITY.get(
                          n.get("node_type", "NORMAL"), 3),
                      reverse=True)

    def mark_tested(self, url: str):
        self.db.mark_tested(url)
        if self.G and url in self.G:
            self.G.nodes[url]["tested"] = True

    def _add_node(self, node: Dict):
        url    = node["url"]
        ntype  = node.get("node_type", "NORMAL")
        params = node.get("params", "[]")
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = []

        if self.G is not None:
            self.G.add_node(url,
                node_type=ntype,
                priority=NODE_PRIORITY.get(ntype, 3),
                params=params,
                tested=bool(node.get("tested")),
                auth_req=bool(node.get("auth_req")),
                sensitive=bool(node.get("sensitive"))
            )

    def _add_edge(self, edge: Dict):
        if self.G is None:
            return
        src  = edge.get("from_url", "")
        dest = edge.get("to_url", "")
        if src and dest:
            self.G.add_edge(src, dest,
                edge_type=edge.get("edge_type", "NAVIGATE"))

    def _infer_edges(self, nodes: List[Dict]):
        """Infer parent→child edges from URL structure."""
        if self.G is None:
            return
        urls = [n["url"] for n in nodes]
        for url in urls:
            parsed = urlparse(url)
            parts  = parsed.path.rstrip("/").split("/")
            if len(parts) > 2:
                parent_path = "/".join(parts[:-1])
                parent_url  = f"{parsed.scheme}://{parsed.netloc}{parent_path}"
                if parent_url in urls and parent_url != url:
                    self.G.add_edge(parent_url, url,
                                    edge_type="NAVIGATE")

    def _save(self, nodes: List[Dict], edges: list):
        path = os.path.join(self.out_dir, f"{self.prefix}_graph.json")
        data = {
            "nodes": [
                {"url": n["url"], "type": n.get("node_type", "NORMAL"),
                 "priority": n.get("priority", 3),
                 "tested": bool(n.get("tested"))}
                for n in nodes
            ],
            "edges": [
                {"from": dict(e).get("from_url"),
                 "to":   dict(e).get("to_url"),
                 "type": dict(e).get("edge_type", "NAVIGATE")}
                for e in edges
            ],
            "stats": {
                "total_nodes": len(nodes),
                "untested":    sum(1 for n in nodes if not n.get("tested"))
            }
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
