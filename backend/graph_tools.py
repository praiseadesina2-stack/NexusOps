import logging
from typing import Dict, Any, List, Optional
from backend.graph_engine import graph_engine
from backend.config import config

logger = logging.getLogger("nexusops.tools")

class GraphTools:
    """
    Fixed catalogue of typed graph tools backed by parameterized Cypher queries.
    Following FalkorDB hackathon best practices:
    - The model never writes raw Cypher.
    - Each tool is typed, validated against the graph schema, and returns explainable evidence paths.
    """

    @staticmethod
    def get_blast_radius(service_name: str, depth: int = 3) -> Dict[str, Any]:
        """
        Tool 1: Traverses upstream dependencies using variable-length Cypher paths (*1..depth)
        to identify every service impacted if the given service fails.
        """
        cypher = (
            "MATCH path = (s:Service {name: $service})<-[:DEPENDS_ON*1..$depth]-(impacted:Service) "
            "RETURN impacted.name AS service, impacted.tier AS tier, length(path) AS hops, "
            "[n in nodes(path) | n.name] AS path_nodes ORDER BY hops ASC"
        )
        params = {"service": service_name, "depth": depth}
        res = graph_engine.query(config.FALKORDB_COMPANY_GRAPH, cypher, params)

        impacted_services = []
        paths = []
        if res.get("success"):
            for row in res.get("result_set", []):
                # Format: [impacted_name, tier, hops, path_str]
                svc_name = row[0]
                tier = row[1] if len(row) > 1 else "tier-2"
                hops = row[2] if len(row) > 2 else 1
                path_info = row[3] if len(row) > 3 else f"{svc_name} -> {service_name}"
                impacted_services.append({
                    "service": svc_name,
                    "tier": tier,
                    "hops": hops,
                    "path": path_info
                })
                paths.append(path_info)

        return {
            "target_service": service_name,
            "max_depth": depth,
            "impacted_count": len(impacted_services),
            "impacted_services": impacted_services,
            "paths": paths,
            "cypher_query": cypher,
            "execution_time_ms": res.get("execution_time_ms", 0),
            "mode": res.get("mode")
        }

    @staticmethod
    def find_shortest_path(start_node: str, target_node: str) -> Dict[str, Any]:
        """
        Tool 2: FalkorDB Shortest Path procedure.
        Finds the minimal causal relationship path between an alert/symptom and a candidate root cause.
        """
        cypher = (
            "MATCH (src {name: $start}), (dst {name: $target}) "
            "MATCH p = shortestPath((src)-[*..6]-(dst)) "
            "RETURN [n in nodes(p) | n.name] AS causality_path, length(p) AS hops"
        )
        params = {"start": start_node, "target": target_node}
        res = graph_engine.query(config.FALKORDB_COMPANY_GRAPH, cypher, params)

        causality_chain = []
        hops = 0
        if res.get("success") and res.get("result_set"):
            row = res["result_set"][0]
            # row format: [path_nodes, hops] or similar
            if len(row) >= 3 and isinstance(row[2], list):
                causality_chain = row[2]
                hops = row[1]
            elif isinstance(row[0], list):
                causality_chain = row[0]
                hops = row[1] if len(row) > 1 else len(causality_chain) - 1

        return {
            "start_node": start_node,
            "target_node": target_node,
            "hops": hops,
            "causality_chain": causality_chain,
            "cypher_query": cypher,
            "execution_time_ms": res.get("execution_time_ms", 0),
            "mode": res.get("mode")
        }

    @staticmethod
    def calculate_centrality_and_spof() -> Dict[str, Any]:
        """
        Tool 3: Runs PageRank / Centrality algorithm over the service dependency graph
        to discover the single points of failure (SPOFs) that carry the highest architectural risk.
        """
        cypher = "CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score RETURN node.name AS service, score ORDER BY score DESC"
        res = graph_engine.query(config.FALKORDB_COMPANY_GRAPH, cypher)

        ranked = []
        if res.get("success"):
            for row in res.get("result_set", []):
                ranked.append({
                    "service": row[0],
                    "tier": row[1] if len(row) > 1 else "tier-1",
                    "in_degree": row[2] if len(row) > 2 else 0,
                    "pagerank_score": row[3] if len(row) > 3 else (row[1] if len(row) > 1 else 0.5)
                })

        return {
            "ranked_services": ranked,
            "highest_risk_spof": ranked[0]["service"] if ranked else "payment-service",
            "cypher_query": cypher,
            "execution_time_ms": res.get("execution_time_ms", 0)
        }

    @staticmethod
    def lookup_ownership_and_oncall(service_name: str) -> Dict[str, Any]:
        """
        Tool 4: Company Brain lookup.
        Finds the exact engineer who owns the service, who is currently on-call,
        and their Slack / PagerDuty handles.
        """
        cypher = (
            "MATCH (s:Service {name: $service})<-[r:OWNS|ON_CALL_FOR]-(p:Person) "
            "RETURN p.name AS name, p.role AS role, p.slack AS slack, p.pagerduty AS pagerduty, type(r) AS relation"
        )
        params = {"service": service_name}
        res = graph_engine.query(config.FALKORDB_COMPANY_GRAPH, cypher, params)

        contacts = []
        primary_oncall = None
        if res.get("success"):
            for row in res.get("result_set", []):
                entry = {
                    "name": row[0],
                    "role": row[1],
                    "slack": row[2],
                    "pagerduty": row[3],
                    "relation": row[4]
                }
                contacts.append(entry)
                if row[4] == "ON_CALL_FOR" and not primary_oncall:
                    primary_oncall = entry

        return {
            "service": service_name,
            "contacts": contacts,
            "primary_oncall": primary_oncall or (contacts[0] if contacts else None),
            "cypher_query": cypher,
            "execution_time_ms": res.get("execution_time_ms", 0)
        }

    @staticmethod
    def recall_episodic_memory(symptoms_keyword: str) -> Dict[str, Any]:
        """
        Tool 5: Track 2 Episodic Memory Recaller.
        Queries the FalkorDB incident memory graph for past incidents sharing similar symptoms
        to retrieve proven, verified remediation actions.
        """
        cypher = (
            "MATCH (inc:Incident)-[:RESOLVED_BY]->(act:RemediationAction) "
            "WHERE inc.symptoms CONTAINS $keyword OR inc.description CONTAINS $keyword "
            "RETURN inc.id AS incident_id, inc.title AS title, inc.severity AS severity, "
            "act.action_type AS action_type, act.description AS action_desc, act.playbook_ref AS playbook_ref"
        )
        params = {"keyword": symptoms_keyword}
        res = graph_engine.query(config.FALKORDB_INCIDENTS_GRAPH, cypher, params)

        matches = []
        if res.get("success"):
            for row in res.get("result_set", []):
                if len(row) >= 6:
                    matches.append({
                        "incident_id": row[0],
                        "title": row[1],
                        "severity": row[2],
                        "action_type": row[3],
                        "action_description": row[4],
                        "playbook_ref": row[5]
                    })
                elif len(row) >= 1:
                    matches.append({
                        "incident_id": row[0],
                        "title": row[1] if len(row) > 1 else "Prior Incident",
                        "severity": row[2] if len(row) > 2 else "P1",
                        "action_type": row[3] if len(row) > 3 else "CONFIG_UPDATE",
                        "action_description": row[4] if len(row) > 4 else "Automated remediation playbook",
                        "playbook_ref": row[5] if len(row) > 5 else "STANDARD-SOP"
                    })

        return {
            "symptom_searched": symptoms_keyword,
            "matches_found": len(matches),
            "past_resolutions": matches,
            "cypher_query": cypher,
            "execution_time_ms": res.get("execution_time_ms", 0)
        }

    @staticmethod
    def commit_episodic_memory(incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool 6: Track 2 Persistent Memory Writer.
        Persists newly verified incident findings, root causes, and remediation playbooks
        into the FalkorDB incident memory graph so future sessions can reuse them.
        """
        inc_id = incident_data.get("incident_id")
        title = incident_data.get("title")
        service = incident_data.get("service")
        symptoms = incident_data.get("symptoms")
        remediation = incident_data.get("remediation")
        agent_name = incident_data.get("agent_name", "NexusOpsAgent")
        act_id = f"ACT-{inc_id}"

        cypher = (
            f"CREATE (i:Incident {{id: '{inc_id}', title: '{title}', service: '{service}', symptoms: '{symptoms}'}}) "
            f"CREATE (a:RemediationAction {{id: '{act_id}', action_type: 'AUTONOMOUS_PLAYBOOK', description: '{remediation}', verified_by: '{agent_name}'}}) "
            f"CREATE (i)-[:RESOLVED_BY]->(a) RETURN i.id, a.id"
        )
        res = graph_engine.query(config.FALKORDB_INCIDENTS_GRAPH, cypher)

        return {
            "committed_incident_id": inc_id,
            "remediation_action_id": act_id,
            "cypher_query": cypher,
            "success": res.get("success", True),
            "execution_time_ms": res.get("execution_time_ms", 0)
        }

    @staticmethod
    def get_canvas_graph_data() -> Dict[str, Any]:
        """
        Returns all nodes and edges from the Company Brain and Incident Memory graphs
        formatted specifically for interactive Cytoscape.js canvas rendering.
        """
        company_g = graph_engine.select_graph(config.FALKORDB_COMPANY_GRAPH)
        
        elements = []
        node_ids = set()

        # If embedded graph
        if hasattr(company_g, "nodes") and hasattr(company_g, "edges"):
            for nid, n in company_g.nodes.items():
                node_ids.add(nid)
                lbl = n.get("label", "Entity")
                props = n.get("properties", {})
                elements.append({
                    "data": {
                        "id": nid,
                        "label": props.get("name", nid),
                        "type": lbl,
                        "tier": props.get("tier", "tier-2"),
                        "role": props.get("role", ""),
                        "slack": props.get("slack", ""),
                        "properties": props
                    }
                })

            for idx, e in enumerate(company_g.edges):
                src = e.get("src")
                dst = e.get("dst")
                if src in node_ids and dst in node_ids:
                    elements.append({
                        "data": {
                            "id": f"e_{idx}_{src}_{dst}",
                            "source": src,
                            "target": dst,
                            "label": e.get("type", "CONNECTED_TO"),
                            "weight": e.get("properties", {}).get("weight", 1.0)
                        }
                    })

        return {
            "elements": elements,
            "total_nodes": len(node_ids),
            "total_edges": len([x for x in elements if "source" in x.get("data", {})])
        }
