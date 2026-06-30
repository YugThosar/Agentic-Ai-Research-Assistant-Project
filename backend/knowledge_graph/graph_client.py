"""
Knowledge Graph client.
Uses NetworkX for local mode, and can be extended to Neo4j in production.
Entities and relationships are extracted via the LLM and persisted as JSON.
"""
import json
import logging
import pickle
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.config import LOCAL_GRAPH_DIR, settings

logger = logging.getLogger("apks.graph")
GRAPH_PATH = LOCAL_GRAPH_DIR / "knowledge_graph.pkl"


class GraphClient:
    """
    In-process knowledge graph backed by NetworkX.
    Nodes represent entities/concepts; edges represent relationships.
    """

    def __init__(self):
        try:
            import networkx as nx
            self.nx = nx
        except ImportError:
            raise ImportError("networkx is required. Run `pip install networkx`.")

        self.graph: Any = None
        self._load()

    def _load(self):
        if GRAPH_PATH.exists():
            with open(GRAPH_PATH, "rb") as f:
                self.graph = pickle.load(f)
            logger.info(f"Loaded knowledge graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges.")
        else:
            self.graph = self.nx.DiGraph()
            logger.info("Created new knowledge graph.")

    def _save(self):
        with open(GRAPH_PATH, "wb") as f:
            pickle.dump(self.graph, f)

    # ------------------------------------------------------------------ #
    # Write operations                                                     #
    # ------------------------------------------------------------------ #
    def add_entity(self, entity_id: str, label: str, entity_type: str, properties: Dict = None):
        self.graph.add_node(entity_id, label=label, type=entity_type, **(properties or {}))

    def add_relationship(self, source_id: str, target_id: str, relation: str, properties: Dict = None):
        self.graph.add_edge(source_id, target_id, label=relation, **(properties or {}))

    def add_triples(self, triples: List[Dict[str, Any]]):
        """
        Bulk ingest triples. Each triple: {"head": str, "relation": str, "tail": str, "doc_id": str}
        """
        for t in triples:
            head = t.get("head", "").strip()
            tail = t.get("tail", "").strip()
            relation = t.get("relation", "related_to").strip()
            doc_id = t.get("doc_id", "")
            if head and tail:
                if not self.graph.has_node(head):
                    self.add_entity(head, head, "Entity")
                if not self.graph.has_node(tail):
                    self.add_entity(tail, tail, "Entity")
                self.add_relationship(head, tail, relation, {"doc_id": doc_id})
        self._save()
        logger.info(f"Added {len(triples)} triples to knowledge graph.")

    def delete_document_nodes(self, doc_id: str):
        """Remove edges (and optionally orphan nodes) associated with a document."""
        edges_to_remove = [
            (u, v) for u, v, d in self.graph.edges(data=True) if d.get("doc_id") == doc_id
        ]
        self.graph.remove_edges_from(edges_to_remove)
        # Remove isolated nodes
        isolated = list(self.nx.isolates(self.graph))
        self.graph.remove_nodes_from(isolated)
        self._save()
        logger.info(f"Removed {len(edges_to_remove)} edges and {len(isolated)} orphan nodes for doc_id={doc_id}.")

    # ------------------------------------------------------------------ #
    # Read operations                                                      #
    # ------------------------------------------------------------------ #
    def get_neighbors(self, entity: str, depth: int = 1) -> List[Dict]:
        """Returns neighboring nodes up to a certain depth."""
        if not self.graph.has_node(entity):
            return []
        neighbors = []
        for n in self.nx.ego_graph(self.graph, entity, radius=depth).nodes():
            node_data = self.graph.nodes[n]
            neighbors.append({"id": n, "label": node_data.get("label", n), "type": node_data.get("type", "Entity")})
        return neighbors

    def search_entities(self, query: str, limit: int = 10) -> List[Dict]:
        """Simple string-match search across node labels."""
        query_lower = query.lower()
        results = []
        for node, data in self.graph.nodes(data=True):
            if query_lower in node.lower() or query_lower in data.get("label", "").lower():
                results.append({"id": node, "label": data.get("label", node), "type": data.get("type", "Entity")})
            if len(results) >= limit:
                break
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to nodes/edges dicts for the frontend."""
        nodes = []
        for node, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node,
                "label": data.get("label", node),
                "type": data.get("type", "Entity"),
                "properties": {k: v for k, v in data.items() if k not in ("label", "type")},
            })
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "label": data.get("label", "related_to"),
                "properties": {k: v for k, v in data.items() if k != "label"},
            })
        return {"nodes": nodes, "edges": edges}


_graph_client: Optional[GraphClient] = None


def get_graph_client() -> GraphClient:
    global _graph_client
    if _graph_client is None:
        _graph_client = GraphClient()
    return _graph_client
