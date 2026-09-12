"""One-time: load the knowledge graph into whichever Neo4j the app will use.

    python scripts/load_graph.py            # build, then verify
    python scripts/load_graph.py --check    # verify only, change nothing

Run this ONCE against your Aura instance before deploying. The app itself never
writes to the graph — it only reads — so this is a setup step, not part of the
request path. Aura keeps the data, so a redeploy does not need to repeat it.

Credentials come from the environment, or from .streamlit/secrets.toml if one
exists, so the same file configures both this script and the deployed app:

    NEO4J_URI=neo4j+s://xxxxxxx.databases.neo4j.io \\
    NEO4J_PASSWORD=... python scripts/load_graph.py

The graph is small — 126 nodes, 266 relationships — and every node and edge is
tagged `demo: 'ffcs_kg'`, so this is safe to run against a database that holds
other things: it only ever touches its own marked subgraph.
"""
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def load_secrets():
    """Read .streamlit/secrets.toml into the environment, if it exists.

    Environment variables already set win, so a one-off override on the command
    line beats the file rather than being silently ignored.
    """
    path = ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return
    for key, value in tomllib.loads(path.read_text()).items():
        if isinstance(value, (str, int, float)) and key not in os.environ:
            os.environ[key] = str(value)
    print(f"Read credentials from {path.relative_to(ROOT)}")


def main():
    load_secrets()
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    print(f"Target: {uri}")

    import build_graph
    import verify_graph

    if "--check" not in sys.argv:
        build_graph.main()
        print()

    # verify_graph prints its 11 checks and raises on a connection problem; it does
    # not return a verdict, so read the output rather than trusting an exit code.
    verify_graph.main()
    print("\nGraph is loaded. Read the checks above, then start the app.")


if __name__ == "__main__":
    main()
