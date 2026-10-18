import logging
from backend.graph_engine import graph_engine
from backend.config import config

logger = logging.getLogger("nexusops.seed")

def seed_graph_database():
    """
    Populates the FalkorDB multigraph instances:
    1. nexus_company_brain: services, infrastructure, ownership, commits, docs.
    2. nexus_incident_memory: episodic memory of past resolved incidents and playbooks.
    """
    logger.info("Initializing Graph Data Model seeding...")

    # Select graphs
    company_g = graph_engine.select_graph(config.FALKORDB_COMPANY_GRAPH)
    incident_g = graph_engine.select_graph(config.FALKORDB_INCIDENTS_GRAPH)

    # -------------------------------------------------------------
    # 1. Populate COMPANY BRAIN GRAPH
    # -------------------------------------------------------------
    services = [
        {"id": "api-gateway", "name": "api-gateway", "tier": "tier-1", "language": "Go", "repo": "org/api-gateway"},
        {"id": "auth-service", "name": "auth-service", "tier": "tier-1", "language": "TypeScript", "repo": "org/auth-service"},
        {"id": "orders-service", "name": "orders-service", "tier": "tier-1", "language": "Python", "repo": "org/orders-service"},
        {"id": "payment-service", "name": "payment-service", "tier": "tier-1", "language": "Rust", "repo": "org/payment-service"},
        {"id": "inventory-service", "name": "inventory-service", "tier": "tier-2", "language": "Go", "repo": "org/inventory-service"},
        {"id": "fraud-detector", "name": "fraud-detector", "tier": "tier-2", "language": "Python", "repo": "org/fraud-detector"},
        {"id": "notification-worker", "name": "notification-worker", "tier": "tier-3", "language": "Node.js", "repo": "org/notification-worker"},
        {"id": "reporting-service", "name": "reporting-service", "tier": "tier-3", "language": "Python", "repo": "org/reporting-service"},
    ]

    infra = [
        {"id": "redis-session-cache", "name": "redis-session-cache", "tier": "tier-1", "type": "Cache"},
        {"id": "postgres-payments", "name": "postgres-payments", "tier": "tier-1", "type": "Database"},
        {"id": "kafka-event-bus", "name": "kafka-event-bus", "tier": "tier-1", "type": "Broker"},
        {"id": "postgres-inventory", "name": "postgres-inventory", "tier": "tier-2", "type": "Database"},
    ]

    people = [
        {"id": "sarah-chen", "name": "Sarah Chen", "role": "Principal Platform Eng", "slack": "@sarah.c", "pagerduty": "PD-SARAH-P0"},
        {"id": "marcus-vance", "name": "Marcus Vance", "role": "Staff Backend Eng", "slack": "@marcus.v", "pagerduty": "PD-MARCUS-P1"},
        {"id": "elena-rostova", "name": "Elena Rostova", "role": "Senior SRE", "slack": "@elena.sre", "pagerduty": "PD-ELENA-SRE"},
        {"id": "devon-brooks", "name": "Devon Brooks", "role": "Security Analyst", "slack": "@devon.b", "pagerduty": "PD-DEVON-SEC"},
    ]

    commits = [
        {
            "id": "commit-c891a",
            "name": "commit-c891a",
            "hash": "c891af4",
            "message": "perf: tighten Redis connection pool timeout to 450ms for payment-service",
            "timestamp": "2026-10-15T16:20:00Z",
            "author": "Sarah Chen"
        },
        {
            "id": "commit-d442e",
            "name": "commit-d442e",
            "hash": "d442e91",
            "message": "feat: add optimistic concurrency locking to inventory checkout",
            "timestamp": "2026-10-15T11:00:00Z",
            "author": "Marcus Vance"
        }
    ]

    docs = [
        {"id": "ADR-042", "name": "ADR-042", "title": "ADR-042: Distributed Sagas with Kafka & Ledger", "type": "ADR"},
        {"id": "RUNBOOK-019", "name": "RUNBOOK-019", "title": "RUNBOOK-019: Payment Gateway Circuit Breakers & Connection Pool Recovery", "type": "Runbook"},
        {"id": "DOC-108", "name": "DOC-108", "title": "DOC-108: Tier-1 SLA Thresholds & Escalation Hierarchy", "type": "SLA"},
    ]

    dependencies = [
        ("api-gateway", "auth-service", "DEPENDS_ON", {"type": "sync", "weight": 1.0}),
        ("api-gateway", "orders-service", "DEPENDS_ON", {"type": "sync", "weight": 1.0}),
        ("orders-service", "auth-service", "DEPENDS_ON", {"type": "sync", "weight": 1.0}),
        ("orders-service", "payment-service", "DEPENDS_ON", {"type": "sync", "weight": 2.5}),
        ("orders-service", "inventory-service", "DEPENDS_ON", {"type": "sync", "weight": 1.2}),
        ("payment-service", "postgres-payments", "DEPENDS_ON", {"type": "storage", "weight": 3.0}),
        ("payment-service", "redis-session-cache", "DEPENDS_ON", {"type": "cache", "weight": 2.0}),
        ("payment-service", "fraud-detector", "DEPENDS_ON", {"type": "async", "weight": 1.0}),
        ("auth-service", "redis-session-cache", "DEPENDS_ON", {"type": "cache", "weight": 2.0}),
        ("inventory-service", "postgres-inventory", "DEPENDS_ON", {"type": "storage", "weight": 2.0}),
        ("orders-service", "kafka-event-bus", "DEPENDS_ON", {"type": "pubsub", "weight": 1.0}),
        ("kafka-event-bus", "notification-worker", "DEPENDS_ON", {"type": "async", "weight": 1.0}),
        ("kafka-event-bus", "reporting-service", "DEPENDS_ON", {"type": "async", "weight": 1.0}),
    ]

    ownerships = [
        ("sarah-chen", "payment-service", "OWNS"),
        ("sarah-chen", "auth-service", "OWNS"),
        ("sarah-chen", "payment-service", "ON_CALL_FOR"),
        ("marcus-vance", "orders-service", "OWNS"),
        ("marcus-vance", "inventory-service", "OWNS"),
        ("marcus-vance", "orders-service", "ON_CALL_FOR"),
        ("elena-rostova", "api-gateway", "OWNS"),
        ("elena-rostova", "redis-session-cache", "OWNS"),
        ("elena-rostova", "kafka-event-bus", "OWNS"),
        ("elena-rostova", "api-gateway", "ON_CALL_FOR"),
        ("devon-brooks", "fraud-detector", "OWNS"),
    ]

    commit_links = [
        ("commit-c891a", "payment-service", "TOUCHED"),
        ("sarah-chen", "commit-c891a", "AUTHORED"),
        ("commit-d442e", "inventory-service", "TOUCHED"),
        ("marcus-vance", "commit-d442e", "AUTHORED"),
    ]

    doc_links = [
        ("RUNBOOK-019", "payment-service", "COVERS"),
        ("RUNBOOK-019", "redis-session-cache", "COVERS"),
        ("ADR-042", "orders-service", "COVERS"),
        ("DOC-108", "api-gateway", "COVERS"),
    ]

    # Populate in embedded engine for local resilience
    for s in services:
        company_g.add_node(s["id"], "Service", s)
    for inf in infra:
        company_g.add_node(inf["id"], "Infrastructure", inf)
    for p in people:
        company_g.add_node(p["id"], "Person", p)
    for c in commits:
        company_g.add_node(c["id"], "Commit", c)
    for d in docs:
        company_g.add_node(d["id"], "Document", d)

    for src, dst, rel, props in dependencies:
        company_g.add_edge(src, dst, rel, props)
    for src, dst, rel in ownerships:
        company_g.add_edge(src, dst, rel)
    for src, dst, rel in commit_links:
        company_g.add_edge(src, dst, rel)
    for src, dst, rel in doc_links:
        company_g.add_edge(src, dst, rel)

    # -------------------------------------------------------------
    # 2. Populate INCIDENT MEMORY GRAPH (Episodic Memory)
    # -------------------------------------------------------------
    past_incidents = [
        {
            "id": "INC-842",
            "name": "INC-842",
            "title": "Payment Service Redis Connection Pool Timeout under Flash Surge",
            "severity": "P0",
            "service": "payment-service",
            "symptoms": "HTTP 504 Gateway Timeout, connection pool exhaustion timeout, redis connection timeout",
            "description": "Payment transactions failed due to aggressive pool timeout settings (450ms) exhausting connection pool.",
            "resolved_at": "2026-09-12T14:32:00Z"
        },
        {
            "id": "INC-719",
            "name": "INC-719",
            "title": "Kafka Consumer Lag Surge during Inventory Reconciliation",
            "severity": "P1",
            "service": "notification-worker",
            "symptoms": "Message lag growing exponentially on topic order.created, consumer rebalance storm",
            "description": "Notification worker batch size caused timeout before poll completed.",
            "resolved_at": "2026-08-04T09:15:00Z"
        }
    ]

    remediations = [
        {
            "id": "ACT-842",
            "name": "ACT-842",
            "action_type": "HOTFIX_REVERT_AND_SCALE",
            "description": "Increase Redis connection pool timeout to 2500ms, set max_connections to 64, and trigger graceful rolling restart.",
            "playbook_ref": "RUNBOOK-019 Section 3.2",
            "rollback_cmd": "kubectl rollout undo deployment/payment-service"
        },
        {
            "id": "ACT-719",
            "name": "ACT-719",
            "action_type": "CONFIG_UPDATE",
            "description": "Increase max.poll.interval.ms to 600000ms and rebalance consumer group partitions.",
            "playbook_ref": "RUNBOOK-044 Section 1.1",
            "rollback_cmd": "kafka-consumer-groups --bootstrap-server kafka:9092 --reset-offsets"
        }
    ]

    for inc in past_incidents:
        incident_g.add_node(inc["id"], "Incident", inc)
    for act in remediations:
        incident_g.add_node(act["id"], "RemediationAction", act)

    incident_g.add_edge("INC-842", "ACT-842", "RESOLVED_BY", {"verified_by": "SentinelAgent", "confidence": 0.98})
    incident_g.add_edge("INC-719", "ACT-719", "RESOLVED_BY", {"verified_by": "RemediationAgent", "confidence": 0.95})

    # If FalkorDB live instance is connected, write Cypher seed queries directly into FalkorDB!
    if graph_engine.is_connected and graph_engine.client:
        try:
            logger.info("Executing Cypher seed queries into live FalkorDB instance...")
            # Seed Company Brain in FalkorDB
            cg = graph_engine.client.select_graph(config.FALKORDB_COMPANY_GRAPH)
            for s in services:
                cg.query("MERGE (s:Service {name: $name}) SET s.tier = $tier, s.language = $language, s.repo = $repo", s)
            for inf in infra:
                cg.query("MERGE (i:Infrastructure {name: $name}) SET i.tier = $tier, i.type = $type", inf)
            for p in people:
                cg.query("MERGE (p:Person {name: $name}) SET p.role = $role, p.slack = $slack, p.pagerduty = $pagerduty", p)
            for c in commits:
                cg.query("MERGE (c:Commit {name: $name}) SET c.hash = $hash, c.message = $message, c.author = $author", c)
            for d in docs:
                cg.query("MERGE (d:Document {name: $name}) SET d.title = $title, d.type = $type", d)
            
            for src, dst, rel, props in dependencies:
                cg.query(f"MATCH (a {{name: $src}}), (b {{name: $dst}}) MERGE (a)-[r:{rel}]->(b) SET r.weight = $w, r.type = $t", 
                         {"src": src, "dst": dst, "w": props.get("weight", 1.0), "t": props.get("type", "sync")})
            for src, dst, rel in ownerships:
                cg.query(f"MATCH (a {{id: $src}}), (b {{name: $dst}}) MERGE (a)-[:{rel}]->(b)", {"src": src, "dst": dst})
            
            # Seed Incident Memory in FalkorDB
            ig = graph_engine.client.select_graph(config.FALKORDB_INCIDENTS_GRAPH)
            for inc in past_incidents:
                ig.query("MERGE (i:Incident {id: $id}) SET i.title = $title, i.severity = $severity, i.symptoms = $symptoms, i.description = $description", inc)
            for act in remediations:
                ig.query("MERGE (a:RemediationAction {id: $id}) SET a.action_type = $action_type, a.description = $description, a.playbook_ref = $playbook_ref", act)
            ig.query("MATCH (i:Incident {id: 'INC-842'}), (a:RemediationAction {id: 'ACT-842'}) MERGE (i)-[:RESOLVED_BY]->(a)")
            ig.query("MATCH (i:Incident {id: 'INC-719'}), (a:RemediationAction {id: 'ACT-719'}) MERGE (i)-[:RESOLVED_BY]->(a)")
            logger.info("Live FalkorDB multigraph seeding completed successfully!")
        except Exception as e:
            logger.error(f"FalkorDB Cypher seeding encountered an error: {e}")

    logger.info("Graph seeding complete. Ready for agent operations.")

if __name__ == "__main__":
    seed_graph_database()
