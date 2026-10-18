import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))
    FALKORDB_USERNAME: str = os.getenv("FALKORDB_USERNAME", "default")
    FALKORDB_PASSWORD: str = os.getenv("FALKORDB_PASSWORD", "")
    
    # Multigraph Names
    FALKORDB_COMPANY_GRAPH: str = os.getenv("FALKORDB_COMPANY_GRAPH", "nexus_company_brain")
    FALKORDB_INCIDENTS_GRAPH: str = os.getenv("FALKORDB_INCIDENTS_GRAPH", "nexus_incident_memory")
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

config = Config()
