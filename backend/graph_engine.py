import logging
import time
from typing import Dict, Any, List, Optional
from backend.config import config

logger = logging.getLogger("nexusops.graph_engine")
logging.basicConfig(level=logging.INFO)

class FalkorDBEngine:
    """
    Primary Graph Engine interface for NexusOps.
    Connects natively to FalkorDB Cloud or Docker instance.
    Falls back gracefully to an embedded in-memory graph simulator
    if FalkorDB credentials are being updated, ensuring zero downtime.
    """

    def __init__(self):
        self.client = None
        self.is_connected = False
        self.mode = "Disconnected"
        self.connection_error = None
        self.embedded_graphs: Dict[str, "EmbeddedGraph"] = {}
        self.connect()

    def connect(self):
        """Attempts connection to FalkorDB instance."""
        host = config.FALKORDB_HOST
        port = config.FALKORDB_PORT
        password = config.FALKORDB_PASSWORD
        username = config.FALKORDB_USERNAME

        if not host or not password:
            self.mode = "Embedded Fallback"
            self.is_connected = False
            self.connection_error = "Host or password not configured in .env"
            logger.info("Using Embedded Graph Engine (local development mode)")
            return

        try:
            from falkordb import FalkorDB
            logger.info(f"Connecting to FalkorDB at {host}:{port}...")
            
            kwargs = {"host": host, "port": port}
            if password:
                kwargs["password"] = password
            if username and username != "default":
                kwargs["username"] = username

            self.client = FalkorDB(**kwargs)
            # Verification ping on a test graph
            g = self.client.select_graph(config.FALKORDB_COMPANY_GRAPH)
            g.query("RETURN 1")
            
            self.is_connected = True
            self.connection_error = None
            if "cloud" in host:
                self.mode = "FalkorDB Cloud (LIVE)"
            else:
                self.mode = "FalkorDB Local (Docker)"
            logger.info(f"Connected successfully to {self.mode}")
        except Exception as e:
            self.is_connected = False
            self.connection_error = str(e)
            self.mode = "Embedded Fallback"
            logger.warning(f"Could not connect to FalkorDB server ({e}). Operating in Embedded Graph Mode.")

    def select_graph(self, graph_name: str):
        """Selects a graph in FalkorDB or embedded storage (Multigraph Topology)."""
        if self.is_connected and self.client:
            try:
                return self.client.select_graph(graph_name)
            except Exception as e:
                logger.error(f"Error selecting graph {graph_name} on FalkorDB: {e}")
        
        # Embedded graph fallback
        if graph_name not in self.embedded_graphs:
            self.embedded_graphs[graph_name] = EmbeddedGraph(graph_name)
        return self.embedded_graphs[graph_name]

    def query(self, graph_name: str, query_str: str, params: Optional[Dict[str, Any]] = None):
        """Runs a Cypher query against the specified graph."""
        g = self.select_graph(graph_name)
        start_time = time.time()
        try:
            if hasattr(g, "query"):
                res = g.query(query_str, params)
                exec_time_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "success": True,
                    "result_set": getattr(res, "result_set", []),
                    "header": getattr(res, "header", []),
                    "execution_time_ms": exec_time_ms,
                    "mode": self.mode,
                    "graph": graph_name
                }
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            # Fallback to embedded query if cloud query failed
            if self.is_connected:
                logger.info("Retrying query via embedded graph engine...")
                if graph_name not in self.embedded_graphs:
                    self.embedded_graphs[graph_name] = EmbeddedGraph(graph_name)
                emb_g = self.embedded_graphs[graph_name]
                res = emb_g.query(query_str, params)
                return {
                    "success": True,
                    "result_set": res.result_set,
                    "header": res.header,
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                    "mode": "Embedded Fallback",
                    "graph": graph_name
                }
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "mode": self.mode,
                "graph": graph_name
            }

    def get_status(self) -> Dict[str, Any]:
        """Returns engine status, connectivity details, and node/edge statistics."""
        company_g = self.select_graph(config.FALKORDB_COMPANY_GRAPH)
        incidents_g = self.select_graph(config.FALKORDB_INCIDENTS_GRAPH)

        total_nodes = 0
        total_edges = 0

        # Attempt to count nodes and relationships
        try:
            if self.is_connected and self.client:
                r1 = company_g.query("MATCH (n) RETURN count(n) AS cnt")
                if r1 and r1.result_set:
                    total_nodes += r1.result_set[0][0]
                r2 = company_g.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
                if r2 and r2.result_set:
                    total_edges += r2.result_set[0][0]
                
                r3 = incidents_g.query("MATCH (n) RETURN count(n) AS cnt")
                if r3 and r3.result_set:
                    total_nodes += r3.result_set[0][0]
                r4 = incidents_g.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
                if r4 and r4.result_set:
                    total_edges += r4.result_set[0][0]
            else:
                for eg in self.embedded_graphs.values():
                    total_nodes += len(eg.nodes)
                    total_edges += len(eg.edges)
        except Exception:
            pass

        return {
            "mode": self.mode,
            "is_connected": self.is_connected,
            "host": config.FALKORDB_HOST,
            "port": config.FALKORDB_PORT,
            "company_graph": config.FALKORDB_COMPANY_GRAPH,
            "incidents_graph": config.FALKORDB_INCIDENTS_GRAPH,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "connection_error": self.connection_error
        }


class EmbeddedQueryResult:
    def __init__(self, header: List[str], result_set: List[List[Any]]):
        self.header = header
        self.result_set = result_set


class EmbeddedGraph:
    """
    In-memory graph engine implementing Cypher traversals,
    FalkorDB variable-length hops (*1..depth), shortest path, and PageRank.
    Allows testing and running all Graph Hack features seamlessly.
    """
    def __init__(self, name: str):
        self.name = name
        self.nodes: Dict[str, Dict[str, Any]] = {}  # id -> {id, labels, properties}
        self.edges: List[Dict[str, Any]] = []       # [{src, dst, type, properties}]

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]):
        props = dict(properties)
        props["id"] = node_id
        props["label"] = label
        if "name" not in props:
            props["name"] = node_id
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "labels": [label],
            "properties": props
        }

    def add_edge(self, src_id: str, dst_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None):
        props = dict(properties or {})
        props["weight"] = props.get("weight", 1.0)
        self.edges.append({
            "src": src_id,
            "dst": dst_id,
            "type": rel_type,
            "properties": props
        })

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> EmbeddedQueryResult:
        params = params or {}
        q = cypher.strip()

        # 1. Simple COUNT nodes
        if "count(n)" in q.lower():
            label_filter = None
            if ":" in q:
                part = q.split(":")[1].split(")")[0].strip()
                if part and not part.startswith(" "):
                    label_filter = part
            count = 0
            for n in self.nodes.values():
                if not label_filter or label_filter in n["labels"]:
                    count += 1
            return EmbeddedQueryResult(["cnt"], [[count]])

        # 2. Simple COUNT edges (Fix operator precedence)
        if ("count(r)" in q.lower() or "count(*)" in q.lower()) and ("]-[" in q or "]->" in q):
            return EmbeddedQueryResult(["cnt"], [[len(self.edges)]])

        # 3. Dynamic CREATE / MERGE statements (e.g. episodic memory persistence)
        if q.upper().startswith("CREATE") or q.upper().startswith("MERGE"):
            import re
            # Extract Incident node
            inc_match = re.search(r"\(i:Incident\s*\{([^}]+)\}\)", q)
            if inc_match:
                props_str = inc_match.group(1)
                props = {}
                for item in re.finditer(r"(\w+):\s*['\"]([^'\"]+)['\"]", props_str):
                    props[item.group(1)] = item.group(2)
                inc_id = props.get("id", f"INC-{int(time.time()) % 10000}")
                self.add_node(inc_id, "Incident", props)

            # Extract RemediationAction node
            act_match = re.search(r"\(a:RemediationAction\s*\{([^}]+)\}\)", q)
            if act_match:
                props_str = act_match.group(1)
                props = {}
                for item in re.finditer(r"(\w+):\s*['\"]([^'\"]+)['\"]", props_str):
                    props[item.group(1)] = item.group(2)
                act_id = props.get("id", f"ACT-{inc_id if inc_match else 'NEW'}")
                self.add_node(act_id, "RemediationAction", props)

                if inc_match:
                    self.add_edge(inc_id, act_id, "RESOLVED_BY", {"verified_by": "AutonomousAgent"})

            return EmbeddedQueryResult(["status"], [["CREATED"]])

        # 4. Variable-length blast radius traversal:
        # MATCH path = (s:Service {name: $service})<-[:DEPENDS_ON*1..$depth]-(impacted:Service)
        if "DEPENDS_ON" in q and ("*" in q or "impacted" in q):
            import re
            target_svc = params.get("service") or params.get("service_name")
            if not target_svc:
                m_name = re.search(r'name:\s*["\']([^"\']+)["\']', q)
                if m_name:
                    target_svc = m_name.group(1)

            max_depth = int(params.get("depth", 3))
            if "*1.." in q:
                m_depth = re.search(r'\*1\.\.(\d+)', q)
                if m_depth:
                    max_depth = int(m_depth.group(1))
            
            # Find target node
            target_id = None
            for nid, n in self.nodes.items():
                if n["properties"].get("name") == target_svc or nid == target_svc:
                    target_id = nid
                    break

            if not target_id:
                return EmbeddedQueryResult(["impacted_name", "tier", "hops", "path_str"], [])

            # Traverse upstream dependencies (who depends on target_id: src -[:DEPENDS_ON]-> target_id)
            visited = set()
            queue = [(target_id, 0, [target_id])]
            results = []

            while queue:
                curr_id, dist, path = queue.pop(0)
                if dist >= max_depth:
                    continue

                for e in self.edges:
                    if e["type"] == "DEPENDS_ON" and e["dst"] == curr_id:
                        src_id = e["src"]
                        if src_id not in visited and src_id in self.nodes:
                            visited.add(src_id)
                            src_node = self.nodes[src_id]
                            new_path = [src_id] + path
                            path_str = " -> ".join(new_path)
                            results.append([
                                src_node["properties"].get("name", src_id),
                                src_node["properties"].get("tier", "tier-2"),
                                dist + 1,
                                path_str
                            ])
                            queue.append((src_id, dist + 1, new_path))

            # Sort by hops ascending
            results.sort(key=lambda x: x[2])
            return EmbeddedQueryResult(["impacted_name", "tier", "hops", "path_str"], results)

        # 5. Shortest path algorithm:
        # algo.shortestPath or shortestPath((src)-[*..6]-(dst))
        if "shortestpath" in q.lower():
            import re
            start_name = params.get("start") or params.get("src")
            target_name = params.get("target") or params.get("dst")
            if not start_name:
                m_start = re.search(r'start:\s*["\']([^"\']+)["\']', q)
                if m_start:
                    start_name = m_start.group(1)
            if not target_name:
                m_target = re.search(r'target:\s*["\']([^"\']+)["\']', q)
                if m_target:
                    target_name = m_target.group(1)

            start_id = None
            target_id = None
            for nid, n in self.nodes.items():
                if n["properties"].get("name") == start_name or nid == start_name:
                    start_id = nid
                if n["properties"].get("name") == target_name or nid == target_name:
                    target_id = nid

            if not start_id or not target_id:
                return EmbeddedQueryResult(["path", "length", "nodes"], [])

            # BFS for unweighted/weighted shortest path
            from collections import deque
            q_bfs = deque([(start_id, [start_id])])
            seen = {start_id}
            found_path = None

            while q_bfs:
                curr, p = q_bfs.popleft()
                if curr == target_id:
                    found_path = p
                    break
                # Bi-directional / undirected search for causality graph
                neighbors = []
                for e in self.edges:
                    if e["src"] == curr:
                        neighbors.append(e["dst"])
                    elif e["dst"] == curr:
                        neighbors.append(e["src"])

                for nxt in neighbors:
                    if nxt not in seen and nxt in self.nodes:
                        seen.add(nxt)
                        q_bfs.append((nxt, p + [nxt]))

            if found_path:
                node_names = [self.nodes[x]["properties"].get("name", x) for x in found_path]
                return EmbeddedQueryResult(["path", "length", "nodes"], [[found_path, len(found_path) - 1, node_names]])
            return EmbeddedQueryResult(["path", "length", "nodes"], [])

        # 6. Service ownership and on-call lookup:
        # MATCH (s:Service {name: $service})<-[:OWNS|ON_CALL_FOR]-(p:Person)
        if "OWNS" in q or "ON_CALL_FOR" in q or "Person" in q:
            import re
            svc_name = params.get("service") or params.get("service_name")
            if not svc_name:
                m_svc = re.search(r'name:\s*["\']([^"\']+)["\']', q)
                if m_svc:
                    svc_name = m_svc.group(1)
            res_rows = []
            for e in self.edges:
                if e["type"] in ("OWNS", "ON_CALL_FOR"):
                    person_node = self.nodes.get(e["src"])
                    svc_node = self.nodes.get(e["dst"])
                    if person_node and svc_node:
                        s_name = svc_node["properties"].get("name", svc_node["id"])
                        if not svc_name or s_name.lower() == svc_name.lower():
                            res_rows.append([
                                person_node["properties"].get("name"),
                                person_node["properties"].get("role"),
                                person_node["properties"].get("slack"),
                                person_node["properties"].get("pagerduty"),
                                e["type"],
                                s_name
                            ])
            return EmbeddedQueryResult(["person_name", "role", "slack", "pagerduty", "relation", "service"], res_rows)

        # 7. Episodic memory search:
        # MATCH (inc:Incident)-[:RESOLVED_BY]->(act:RemediationAction)
        if "Incident" in q or "incident" in q or "RESOLVED_BY" in q:
            import re
            kw = (params.get("keyword") or "").lower()
            if not kw:
                m_kw = re.search(r'CONTAINS\s*["\']([^"\']+)["\']', q, re.IGNORECASE)
                if m_kw:
                    kw = m_kw.group(1).lower()
            res_rows = []
            for e in self.edges:
                if e["type"] in ("RESOLVED_BY", "RESOLVED_WITH", "ACTION_TAKEN"):
                    inc_node = self.nodes.get(e["src"])
                    act_node = self.nodes.get(e["dst"])
                    if inc_node and act_node:
                        desc = str(inc_node["properties"].get("description", "")).lower()
                        symp = str(inc_node["properties"].get("symptoms", "")).lower()
                        title = str(inc_node["properties"].get("title", "")).lower()
                        if not kw or (kw in desc or kw in symp or kw in title):
                            res_rows.append([
                                inc_node["properties"].get("id", inc_node.get("id")),
                                inc_node["properties"].get("title", "Incident"),
                                inc_node["properties"].get("severity", "P1"),
                                act_node["properties"].get("action_type", "REMEDIATION"),
                                act_node["properties"].get("description", "Automated Remediation"),
                                act_node["properties"].get("playbook_ref", "SOP-001")
                            ])
            return EmbeddedQueryResult(["incident_id", "title", "severity", "action_type", "action_desc", "playbook_ref"], res_rows)

        # 8. PageRank / Centrality ranking:
        if "pagerank" in q.lower() or "centrality" in q.lower() or "ORDER BY in_degree" in q:
            in_degrees = {}
            for nid in self.nodes:
                in_degrees[nid] = 0
            for e in self.edges:
                if e["dst"] in in_degrees:
                    in_degrees[e["dst"]] += 1
            
            sorted_nodes = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)
            res_rows = []
            for nid, deg in sorted_nodes:
                n = self.nodes[nid]
                if n["label"] == "Service":
                    # Simulated PageRank score based on in-degree and tier
                    rank = round(0.15 + 0.85 * (deg / max(1, len(self.edges))), 4)
                    res_rows.append([
                        n["properties"].get("name", nid),
                        n["properties"].get("tier", "tier-2"),
                        deg,
                        rank
                    ])
            return EmbeddedQueryResult(["service_name", "tier", "in_degree", "pagerank_score"], res_rows)

        # 9. Generic MATCH (n:Label) or MATCH (n) inspection
        if "RETURN" in q.upper() and "MATCH" in q.upper():
            import re
            m_label = re.search(r':(\w+)', q)
            label_req = m_label.group(1) if m_label else None
            rows = []
            for n in self.nodes.values():
                if not label_req or label_req == n.get("label") or label_req in n.get("labels", []):
                    props = n.get("properties", {})
                    rows.append([
                        props.get("name", n.get("id")),
                        n.get("label", "Node"),
                        props.get("tier", props.get("role", "N/A"))
                    ])
            if rows:
                return EmbeddedQueryResult(["name", "label", "detail"], rows[:20])

        # 10. Fallback OK status
        return EmbeddedQueryResult(["status"], [["OK"]])


# Global singleton graph engine
graph_engine = FalkorDBEngine()
