"""Step 4 baseline: pure vector retrieval, no graph involved.

    python vector_search.py            # Chroma  (default; matches the course notebooks)
    python vector_search.py neo4j      # Neo4j native vector index

Both backends hold the same 18 vectors from the same model, so the ranking is
identical. Only the reported score differs, and that difference is worth a minute
in class:

    Chroma  returns a cosine DISTANCE  -> similarity = 1 - distance
    Neo4j   returns a normalised SCORE -> (cosine + 1) / 2

Same order, different number. A score is only meaningful against its own backend.

This is the naive-RAG leg of the step-6 comparison. Each question declares the
chunk(s) that genuinely contain the answer, so we can see whether retrieval alone
puts the right evidence in front of the LLM.
"""

import sys

from build_vectorstore import embed_query, get_collection, get_model

TOP_K = 3

# (question, chunks that genuinely contain the answer, note)
QUESTIONS = [
    ("Which entrance exam do I need for B.Tech Fashion Technology?",
     ["chunk_p3_02"], "CASE 1 explicit negative"),
    ("What do I need to get into B.Des?",
     ["chunk_p3_06"], "CASE 2 logical structure"),
    ("How is a student admitted to M.Des?",
     [], "CASE 3 not stated in the document"),
    ("Which Academic Council meeting approved the regulation that focused on CAL?",
     ["chunk_p2_05"], "control, single chunk"),
    ("Which facilities belong to the school that offers B.Des?",
     ["chunk_p3_04", "chunk_p3_05"], "multi-hop, split"),
    ("Which regulation version does 4.0 replace and when was it approved?",
     ["chunk_p2_03", "chunk_p2_05"], "multi-hop, split"),
    ("What are the course baskets and what do their abbreviations stand for?",
     ["chunk_p1_01", "chunk_p1_05"], "aggregation, split"),
    ("Which exam does an M.Tech applicant sit?",
     ["chunk_p3_03"], "source contains a contradiction"),
]


def search_chroma(model, question, k=TOP_K):
    """Returns [(chunk_id, page, similarity, text), ...] ranked best first."""
    collection = get_collection()
    result = collection.query(
        query_embeddings=[embed_query(model, question)],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        (cid, meta["page"], 1.0 - dist, doc)          # cosine distance -> similarity
        for cid, meta, dist, doc in zip(
            result["ids"][0], result["metadatas"][0],
            result["distances"][0], result["documents"][0])
    ]


def search_neo4j(model, question, k=TOP_K):
    """Same vectors, stored on the :Chunk nodes instead of in Chroma.

    Requires the optional Neo4j vector index; see the appendix in the README.
    """
    from config import get_driver

    driver, database = get_driver()
    with driver.session(database=database) as session:
        rows = list(session.run("""
            CALL db.index.vector.queryNodes('chunk_embedding', $k, $vec)
            YIELD node, score
            RETURN node.id AS id, node.page AS page, score, node.text AS text
        """, {"k": k, "vec": embed_query(model, question)}))
    driver.close()
    return [(r["id"], r["page"], r["score"], r["text"]) for r in rows]


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "chroma"
    search = {"chroma": search_chroma, "neo4j": search_neo4j}[backend]
    model = get_model()

    print(f"Backend: {backend}   top-k: {TOP_K}")
    hits = misses = 0
    for question, gold, note in QUESTIONS:
        print("\n" + "=" * 94)
        print(f"Q: {question}")
        print(f"   ({note})")
        print("-" * 94)
        results = search(model, question)
        retrieved = [r[0] for r in results]
        for rank, (cid, page, score, text) in enumerate(results, 1):
            mark = " <-- contains the answer" if cid in gold else ""
            print(f"  {rank}. {cid}  p{page}  score={score:.4f}{mark}")
            print(f"     {text[:110].strip()}...")
        if not gold:
            print(f"\n  VERDICT: the answer is not in the corpus. Retrieval still returned "
                  f"{len(results)} chunks, none of which can answer it.")
        else:
            missing = [g for g in gold if g not in retrieved]
            hits += not missing
            misses += bool(missing)
            print(f"\n  VERDICT: {'PASS' if not missing else 'FAIL'}"
                  + (f" — MISSING {missing}" if missing else ""))

    print("\n" + "=" * 94)
    print(f"Pure vector retrieval @ top-{TOP_K} ({backend}): "
          f"{hits} pass, {misses} fail (of {hits + misses} answerable questions)")


if __name__ == "__main__":
    main()
