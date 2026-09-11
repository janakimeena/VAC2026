#!/usr/bin/env bash
#
# Build everything the notebooks need, in order:
#
#     small.pdf  ->  chunks.json  ->  + citations  ->  Neo4j graph
#                                                  ->  Chroma vector store
#
#   ./setup.sh          build everything, then verify it   (safe to re-run)
#   ./setup.sh --check  verify an existing build only, change nothing
#
# Safe to re-run at any time: the graph loader deletes only nodes tagged
# demo:'ffcs_kg' and leaves anything else in the database untouched, and the
# vector store is rebuilt from scratch each time.
#
# The steps are NOT independent. Step 1 rewrites chunks.json WITHOUT citations
# and step 2 puts them back, so a run that stops between the two leaves the
# notebooks half-broken. That is why this script verifies itself at the end
# instead of trusting that every step ran.

set -euo pipefail
cd "$(dirname "$0")"

STEP="start-up"
trap 'rc=$?; echo; echo "!! setup.sh FAILED during: $STEP"; echo;
      echo "   Nothing below this point ran. Read the error above, fix it, then";
      echo "   just run ./setup.sh again - every step is safe to repeat.";
      echo;
      echo "   Common causes are listed under Troubleshooting in README.md.";
      exit $rc' ERR


# --- the verification -------------------------------------------------------
# Checks the three things the notebooks actually open: the chunk file, the
# vector store, and the graph. Each failure names the command that fixes it.

verify() {
  python - <<'PYCHECK'
import json, sys
sys.path.insert(0, "src")
from config import CHUNKS_JSON, CHROMA_DIR, neo4j_settings

ok = True
def report(passed, label, detail, fix):
    global ok
    print(f"  {'PASS' if passed else 'FAIL'}  {label:<22} {detail}")
    if not passed:
        ok = False
        print(f"        fix:  {fix}")

# 1. chunks.json, with the citations step 2 adds
try:
    data = json.loads(CHUNKS_JSON.read_text())
    chunks = data["chunks"]
    cited = sum("citation" in c and "passage" in c for c in chunks)
    reliable = "paragraph_index_reliable" in data["document"]
    report(cited == len(chunks) and reliable, "chunks + citations",
           f"{cited}/{len(chunks)} chunks carry a citation",
           "python src/add_citations.py")
except FileNotFoundError:
    report(False, "chunks + citations", "data/chunks.json is missing",
           "python src/chunk_pdf.py && python src/add_citations.py")
    chunks = []

# 2. the Chroma collection the notebooks open with get_collection()
try:
    import chromadb
    col = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection("ffcs_chunks")
    n = col.count()
    report(n == len(chunks) and n > 0, "vector store",
           f"{n} vectors in collection 'ffcs_chunks'",
           "python src/build_vectorstore.py")
except Exception as e:
    report(False, "vector store", f"{type(e).__name__}: {e}",
           "python src/build_vectorstore.py")

# 3. the graph
try:
    from config import get_driver
    driver, db = get_driver()
    with driver.session(database=db) as s:
        nodes = s.run("MATCH (n {demo:'ffcs_kg'}) RETURN count(n) AS n").single()["n"]
        rels = s.run("MATCH ()-[r {demo:'ffcs_kg'}]->() RETURN count(r) AS n").single()["n"]
    driver.close()
    report(nodes > 0 and rels > 0, "knowledge graph",
           f"{nodes} nodes, {rels} relationships", "python src/build_graph.py")
except Exception as e:
    report(False, "knowledge graph", f"{type(e).__name__}: {e}",
           f"check Neo4j is running and reachable at {neo4j_settings()['uri']}")

sys.exit(0 if ok else 1)
PYCHECK
}


# --- --check: verify only, build nothing ------------------------------------

if [[ "${1:-}" == "--check" ]]; then
  echo "==> checking an existing build (nothing will be rebuilt)"
  echo
  if verify; then
    echo
    echo "All good. Open Jupyter at http://localhost:${JUPYTER_PORT:-8888} -> notebooks/"
    exit 0
  else
    echo
    echo "Something is missing. Either run the single fix command shown above,"
    echo "or rebuild everything with:  ./setup.sh"
    exit 1
  fi
fi


if [[ -n "${1:-}" ]]; then
  echo "setup.sh: unknown option '$1'"
  echo
  echo "  ./setup.sh          build everything, then verify it"
  echo "  ./setup.sh --check  verify an existing build only"
  exit 2
fi


# --- wait for Neo4j ---------------------------------------------------------
# docker compose already waits for the healthcheck, but a hand-started container
# (the no-Docker path in README.md) needs a moment before it accepts bolt.

STEP="waiting for Neo4j"
echo "==> waiting for Neo4j to accept connections"
python - <<'PYWAIT'
import sys, time
sys.path.insert(0, "src")
from config import get_driver, neo4j_settings

uri = neo4j_settings()["uri"]
for attempt in range(30):
    try:
        driver, _ = get_driver()
        driver.close()
        print(f"    connected to {uri}")
        break
    except Exception as e:
        if attempt == 29:
            print(f"    could not reach Neo4j at {uri} after 60s:\n      {e}")
            sys.exit(1)
        time.sleep(2)
PYWAIT


# --- the four build steps ---------------------------------------------------

STEP="1/4 chunking the PDF (src/chunk_pdf.py)"
echo "==> 1/4  chunking the PDF"
python src/chunk_pdf.py

STEP="2/4 adding citations (src/add_citations.py)"
echo "==> 2/4  adding page/passage citations to chunks.json"
python src/add_citations.py | tail -3

STEP="3/4 building the graph (src/build_graph.py)"
echo "==> 3/4  building the knowledge graph"
python src/build_graph.py | tail -8

STEP="4/4 building the vector store (src/build_vectorstore.py)"
echo "==> 4/4  building the vector store"
python src/build_vectorstore.py


# --- verify -----------------------------------------------------------------

STEP="verifying the graph (src/verify_graph.py)"
echo
echo "==> verifying the graph answers correctly"
python src/verify_graph.py | tail -20

trap - ERR          # from here on, report failures through verify() instead

echo
echo "==> verifying everything the notebooks need"
if ! verify; then
  echo
  echo "!! The build finished but the check above did not pass."
  echo "   Run the fix command it printed, then:  ./setup.sh --check"
  exit 1
fi

echo
echo "Ready."
echo "  Jupyter : http://localhost:${JUPYTER_PORT:-8888}   -> notebooks/"
echo "  Neo4j   : http://localhost:${NEO4J_HTTP_PORT:-7474}   (neo4j / ffcsdemo123)"
echo
echo "Re-check at any time with:  ./setup.sh --check"
