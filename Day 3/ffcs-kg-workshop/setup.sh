#!/usr/bin/env bash
# Build the graph and the vector store from scratch. Safe to re-run: the loader
# removes only nodes tagged demo:'ffcs_kg' and leaves anything else untouched.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 1/4  chunking the PDF"
python src/chunk_pdf.py
echo "==> 2/4  adding page/passage citations to chunks.json"
python src/add_citations.py | tail -3
echo "==> 3/4  building the knowledge graph"
python src/build_graph.py | tail -8
echo "==> 4/4  building the vector store"
python src/build_vectorstore.py

echo
echo "==> verifying"
python src/verify_graph.py | tail -20
echo
echo "Ready."
echo "  Jupyter : http://localhost:${JUPYTER_PORT:-8888}"
echo "  Neo4j   : http://localhost:${NEO4J_HTTP_PORT:-7474}   (neo4j / ffcsdemo123)"
