"""Step 4 (Chroma version): build the vector store the students already know.

Two stores, one join key:

    Chroma            id = "chunk_p3_02"   -> embedding + text
    Neo4j  (:Chunk {id: "chunk_p3_02"})    -> graph neighbourhood

Retrieval finds a chunk id in Chroma; the graph is entered through that same id.
That join is the whole mechanism behind hybrid RAG, so it is worth making visible
rather than hiding it inside a single Cypher call.

Embeddings are computed here and passed to Chroma explicitly, rather than letting
Chroma pick its own default model. Students see which model produced the vectors,
and the numbers reproduce exactly in class.
"""

import json
import shutil
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR, CHUNKS_JSON, EMBEDDING_MODEL

MODEL_NAME = EMBEDDING_MODEL
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
COLLECTION = "ffcs_chunks"


def get_model():
    return SentenceTransformer(MODEL_NAME)


def embed_passages(model, texts):
    """Passages are embedded without the instruction prefix (bge is asymmetric)."""
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_query(model, text):
    """Queries get the instruction prefix. Omitting it costs real recall."""
    return model.encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def get_collection():
    """Open the persisted collection for querying."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION)


def main():
    data = json.loads(CHUNKS_JSON.read_text())
    chunks = data["chunks"]

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)          # rebuild from scratch, so reruns are clean

    print(f"Loading {MODEL_NAME} ...")
    model = get_model()

    print(f"Embedding {len(chunks)} chunks ...")
    embeddings = embed_passages(model, [c["text"] for c in chunks])

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine", "model": MODEL_NAME},
    )
    collection.add(
        ids=[c["id"] for c in chunks],                       # <- the join key
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[{"page": c["page"], "n_chars": c["n_chars"],
                    "citation": c.get("citation", f"page {c['page']}"),
                    "passage": c.get("passage", 0)} for c in chunks],
    )

    print(f"Stored {collection.count()} chunks in {CHROMA_DIR}/ "
          f"({len(embeddings[0])} dims, cosine).")
    print("Ids are the join key into Neo4j: MATCH (c:Chunk {id: $id})")

    sample = collection.get(ids=["chunk_p3_02"], include=["metadatas", "documents"])
    print(f"\nSample — chunk_p3_02 (page {sample['metadatas'][0]['page']}):")
    print(f"  {sample['documents'][0][:100]}...")


if __name__ == "__main__":
    main()
