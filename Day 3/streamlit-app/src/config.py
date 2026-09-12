"""Paths and connection settings for the workshop.

Two things live here so they are defined once:

  * where the data files are, resolved from this file's location, so scripts work
    whatever directory you run them from;
  * how to reach Neo4j and Gemini, read from ENVIRONMENT VARIABLES rather than from
    a checked-in file.

Credentials belong in the environment, never in the repository. Copy `.env.example`
to `.env`, put your own keys in it, and docker compose (or `python-dotenv`) will
load them. `.env` is in `.gitignore` for exactly this reason.
"""
import os
from pathlib import Path

try:                                    # optional: lets bare `python src/...` see .env too
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

PDF_PATH       = DATA / "small.pdf"
CHUNKS_JSON    = DATA / "chunks.json"
CHUNKS_PREVIEW = DATA / "chunks_preview.md"
CHROMA_DIR     = DATA / "chroma_ffcs"
NAIVE_RESULTS  = DATA / "naive_rag_results.json"
HYBRID_RESULTS = DATA / "hybrid_results.json"

# Embedding model. Local and deterministic, so results reproduce exactly in class
# and cost no API quota. Baked into the Docker image at build time.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIMS = 384

# Generation model. Free-tier daily quotas are small; if one is exhausted, try
# another id here rather than waiting for the quota to reset.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

DEMO = "ffcs_kg"        # marker on every node and edge this workshop creates


def neo4j_settings():
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.environ.get("NEO4J_USERNAME", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", "ffcsdemo123"),
        "database": os.environ.get("NEO4J_DATABASE", "neo4j"),
    }


def get_driver():
    """Returns (driver, database_name). Remember to close the driver."""
    from neo4j import GraphDatabase
    s = neo4j_settings()
    driver = GraphDatabase.driver(s["uri"], auth=(s["user"], s["password"]))
    driver.verify_connectivity()
    return driver, s["database"]


def google_api_key():
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set.\n"
            "  Copy .env.example to .env and add your key from "
            "https://aistudio.google.com/apikey\n"
            "  Only the two notebooks' live-answer cells need it. Everything else - "
            "the graph, the vector store,\n  the coverage test and the ablation - runs "
            "offline, and the notebooks open with recorded answers."
        )
    return key
