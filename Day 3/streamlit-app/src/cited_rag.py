"""Naive RAG that cites its sources, and verifies the citations it produces.

A citation the model invents is worse than no citation, because it looks
authoritative. So every quote the model returns is checked against the text of the
chunk it claims to be quoting. Unverified quotes are reported, not hidden.

Citation format returned to the reader:

    [page 3, passage 2 of 6] "There is NO Entrance Examination."
"""
import json
import re
import time

from google import genai
from google.genai import errors

from build_vectorstore import embed_query, get_collection, get_model
from config import CHUNKS_JSON, GEMINI_MODEL, google_api_key

MODEL = GEMINI_MODEL

PROMPT = """Answer the question using ONLY the context passages below.

Rules:
1. Be concise (1-4 sentences).
2. After each factual claim, cite the passage it came from using its tag, e.g. [chunk_p3_02].
3. Then, under a line "SOURCES:", list one line per passage you used, in this exact form:
   chunk_id | verbatim sentence copied exactly from that passage
4. Copy the sentence EXACTLY as it appears. Do not paraphrase it.
5. If the context does not contain the answer, say so explicitly and give no sources.

Context:
{context}

Question: {question}
Answer:"""

_chunks = {c["id"]: c for c in json.loads(CHUNKS_JSON.read_text())["chunks"]}


def _normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def cited_rag(question, k=4, model=None, collection=None, client=None, retries=6):
    model = model or get_model()
    collection = collection or get_collection()
    client = client or genai.Client(api_key=google_api_key())

    hit = collection.query(query_embeddings=[embed_query(model, question)],
                           n_results=k, include=["documents", "metadatas"])
    ids, docs = hit["ids"][0], hit["documents"][0]
    context = "\n\n".join(f"[{i}] {d}" for i, d in zip(ids, docs))

    text = None
    for _ in range(retries):
        try:
            text = (client.models.generate_content(
                model=MODEL,
                contents=PROMPT.format(context=context, question=question)).text or "").strip()
            break
        except (errors.ClientError, errors.ServerError) as e:
            # 429 = rate limit, 5xx = transient server error. Both are worth retrying.
            if "429" in str(e) or isinstance(e, errors.ServerError):
                time.sleep(14)
                continue
            raise
    if text is None:
        return {"model": MODEL, "question": question, "retrieved": ids, "answer": "<rate limited>",
                "citations": [], "unverified": []}

    answer, _, sources_block = text.partition("SOURCES:")

    citations, unverified = [], []
    for line in sources_block.strip().splitlines():
        if "|" not in line:
            continue
        cid, _, quote = line.partition("|")
        cid, quote = cid.strip().strip("[]"), quote.strip().strip('"')
        chunk = _chunks.get(cid)
        if chunk is None:
            unverified.append((cid, quote, "unknown chunk id"))
            continue
        # the model must be quoting text that is actually in that chunk
        if _normalise(quote) and _normalise(quote) in _normalise(chunk["text"]):
            citations.append({"chunk": cid, "citation": chunk["citation"],
                              "page": chunk["page"], "quote": quote})
        else:
            unverified.append((cid, quote, "quote not found in that passage"))

    return {"model": MODEL, "question": question, "retrieved": ids, "answer": answer.strip(),
            "citations": citations, "unverified": unverified}


def show(result):
    print(f"Q: {result['question']}")
    print(f"   retrieved: {result['retrieved']}\n")
    print(f"   {result['answer']}\n")
    if result["citations"]:
        print("   SOURCES (verified against the document):")
        for c in result["citations"]:
            print(f"     [{c['citation']}]")
            print(f'       "{c["quote"]}"')
    else:
        print("   SOURCES: none")
    for cid, quote, reason in result["unverified"]:
        print(f"   !! UNVERIFIED CITATION [{cid}] - {reason}")
        print(f'      claimed: "{quote[:90]}"')


if __name__ == "__main__":
    for q in ["Which entrance exam must a B.Tech Fashion Technology applicant take?",
              "What do I need to get into B.Des?"]:
        print("=" * 96)
        show(cited_rag(q))
        print()
        time.sleep(13)
