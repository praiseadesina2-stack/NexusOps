import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Optional

from backend.config import config
from backend.graph_engine import graph_engine
from backend.seed_data import seed_graph_database
from backend.graph_tools import GraphTools
from backend.agents import swarm

logger = logging.getLogger("nexusops.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="NexusOps: Autonomous Incident Commander & Enterprise Knowledge Brain",
    description="FalkorDB-powered multi-agent incident triage, graph causality reasoning, and episodic memory.",
    version="1.0.0"
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Seed graph data model on application boot."""
    logger.info("NexusOps backend initializing...")
    seed_graph_database()
    logger.info("NexusOps backend ready.")

# -------------------------------------------------------------
# Request Models
# -------------------------------------------------------------
class ConnectRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = "default"
    password: Optional[str] = None

class IncidentSimulateRequest(BaseModel):
    service: str = "payment-service"
    alert_title: str = "Payment Service P0 Alert: 504 Gateway Timeouts"
    metric_value: str = "18.4% error rate (HTTP 504), pool saturation > 98%"

class CypherQueryRequest(BaseModel):
    graph: Optional[str] = "nexus_company_brain"
    query: str
    params: Optional[Dict[str, Any]] = None

class BlastRadiusRequest(BaseModel):
    service: str
    depth: Optional[int] = 3

class ShortestPathRequest(BaseModel):
    start_node: str
    target_node: str

class MemorySearchRequest(BaseModel):
    keyword: str

# -------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------
@app.get("/api/status")
async def get_system_status():
    """Returns database connection mode, endpoint details, and multigraph metrics."""
    return graph_engine.get_status()

@app.post("/api/connect")
async def update_connection(req: ConnectRequest):
    """
    Dynamically updates FalkorDB connection credentials and verifies connectivity.
    Enables instant verification when user enters cloud database password.
    """
    if req.host:
        config.FALKORDB_HOST = req.host
    if req.port:
        config.FALKORDB_PORT = req.port
    if req.username:
        config.FALKORDB_USERNAME = req.username
    if req.password is not None:
        config.FALKORDB_PASSWORD = req.password

    # Re-trigger connection and seed live instance if successful
    graph_engine.connect()
    if graph_engine.is_connected:
        seed_graph_database()

    return graph_engine.get_status()

@app.get("/api/graph/canvas")
async def get_graph_canvas():
    """Returns all graph elements formatted for Cytoscape.js interactive visualization."""
    return GraphTools.get_canvas_graph_data()

@app.post("/api/incident/simulate")
async def simulate_incident(req: IncidentSimulateRequest):
    """
    Executes the multi-agent incident triage and resolution pipeline.
    Sentinel -> RootCause -> Remediation -> Episodic Memory commit.
    """
    return swarm.run_incident_pipeline({
        "service": req.service,
        "alert_title": req.alert_title,
        "metric_value": req.metric_value
    })

@app.post("/api/tools/blast_radius")
async def api_blast_radius(req: BlastRadiusRequest):
    """Tool 1: Variable-length upstream blast radius calculation."""
    return GraphTools.get_blast_radius(req.service, req.depth)

@app.post("/api/tools/shortest_path")
async def api_shortest_path(req: ShortestPathRequest):
    """Tool 2: Shortest path causality analysis."""
    return GraphTools.find_shortest_path(req.start_node, req.target_node)

@app.get("/api/tools/spof_pagerank")
async def api_spof_pagerank():
    """Tool 3: FalkorDB PageRank & Single Point of Failure identification."""
    return GraphTools.calculate_centrality_and_spof()

@app.get("/api/tools/ownership/{service_name}")
async def api_ownership(service_name: str):
    """Tool 4: Company Brain ownership and on-call engineer lookup."""
    return GraphTools.lookup_ownership_and_oncall(service_name)

@app.post("/api/tools/recall_memory")
async def api_recall_memory(req: MemorySearchRequest):
    """Tool 5: Episodic memory lookup from past incidents."""
    return GraphTools.recall_episodic_memory(req.keyword)

@app.post("/api/cypher/run")
async def api_run_cypher(req: CypherQueryRequest):
    """
    Cypher Query Sandbox: Runs raw or parameterized Cypher queries
    directly against FalkorDB and returns latency, headers, and records.
    """
    graph_name = req.graph or config.FALKORDB_COMPANY_GRAPH
    return graph_engine.query(graph_name, req.query, req.params)

# -------------------------------------------------------------
# Static Frontend Serving
# -------------------------------------------------------------
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
