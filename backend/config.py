import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
LOCAL_DB_DIR = BASE_DIR / "data" / "db"
LOCAL_VECTOR_DIR = BASE_DIR / "data" / "vector"
LOCAL_GRAPH_DIR = BASE_DIR / "data" / "graph"

# Ensure all local storage directories exist
for directory in [UPLOAD_DIR, LOCAL_DB_DIR, LOCAL_VECTOR_DIR, LOCAL_GRAPH_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Agentic Personal Knowledge System"
    DEBUG: bool = True
    PORT: int = 8000
    
    # Storage Mode: "local" (SQLite + FAISS + NetworkX) or "production" (PostgreSQL + Qdrant + Neo4j)
    STORAGE_MODE: str = "local"
    
    # Relational Database
    DATABASE_URL: str = f"sqlite:///{LOCAL_DB_DIR}/apks.db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "apks"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    
    # Vector Database
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    
    # Knowledge Graph
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # LLM Settings
    # Supports "gemini", "openai", "ollama"
    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Embedding Settings
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    # Retrieval Settings
    HYBRID_ALPHA: float = 0.5  # Weight for vector search, 1 - alpha for BM25
    TOP_K: int = 5
    
    # Agent Confidence Threshold
    CONFIDENCE_THRESHOLD: float = 0.80
    MAX_REFINEMENT_LOOPS: int = 2

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

settings = Settings()
