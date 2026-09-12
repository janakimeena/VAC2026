"""Hybrid RAG: vector retrieval for prose, graph traversal for structure.

The two systems fail in opposite directions.

    naive RAG fails when the answer is a property of the WHOLE document
              (counts, exhaustive lists) - top-k is a sample, not a census

    KAG fails when the answer was never modelled as an entity or relationship
              (rationale, objectives, qualitative description) - the ontology is
              a lossy projection of the text

Hybrid gives the LLM both, joined on the chunk id, and so covers both gaps.

Three context blocks are assembled:

  1. PASSAGES        the top-k chunks, with citations          -> prose, nuance
  2. GRAPH FACTS     1-hop neighbourhood of relevant entities  -> structure across chunks
  3. COMPLETE SETS   every member of each relevant entity type -> counts and exhaustive lists

Block 3 is the piece that repairs the counting failures. If entrance exams are
relevant, the graph contributes ALL four, not just the ones that happened to be
retrieved. That is a census, and only the graph can supply it.

The graph is entered from TWO directions, which matters more than it sounds:

  a) from the retrieved chunks  - entities the passages mention
  b) from the question itself   - entity names and TYPE words in the question

Direction (b) is essential. Seeding only from retrieved chunks means hybrid inherits
every retrieval failure: ask "which schools are named?" and if retrieval returns
chunks that mention no school, the graph is never asked about schools at all. Reading
type words out of the question ("schools" -> the School label) lets the graph answer
even when retrieval looked in the wrong place entirely.
"""
import re
import time

from google import genai
from google.genai import errors

from build_vectorstore import embed_query, get_collection, get_model
from cited_rag import _chunks, _normalise
from config import DEMO, GEMINI_MODEL, get_driver, google_api_key

MODEL = GEMINI_MODEL

PROMPT = """Answer the question using the evidence below.

You are given three kinds of evidence:
- PASSAGES: verbatim text from the document. Use these for wording, rationale and nuance.
- GRAPH FACTS: curated relationships extracted from the whole document.
- COMPLETE SETS: exhaustive lists. When a question asks "how many" or "list all",
  trust COMPLETE SETS over the passages, because the passages are only a sample of
  the document while the complete sets cover all of it.

Rules:
1. Be concise (1-4 sentences).
2. Cite passages you quote using their tag, e.g. [chunk_p3_02].
3. Then, under a line "SOURCES:", one line per passage used:
   chunk_id | verbatim sentence copied exactly from that passage
4. If you relied on a complete set or a graph fact rather than a passage, write
   "GRAPH | <the fact>" as a source line instead.
5. If the evidence does not answer the question, say so explicitly.

{context}

Question: {question}
Answer:"""

# The traversal is undirected so we reach neighbours on both sides, but the FACT we
# emit must keep the edge's real direction. Reading direction off the traversal
# instead of off startNode/endNode produced reversed nonsense such as
# "10+2 marks -REQUIRES-> B.Des", which an LLM will happily believe.
NEIGHBOURHOOD = """
MATCH (e)-[:MENTIONED_IN]->(c:Chunk) WHERE c.id IN $ids OR any(l IN $labels WHERE l IN labels(e))
MATCH (e)-[r]-(n)
WHERE NOT n:Chunk AND NOT n:Document AND type(r) <> 'MENTIONED_IN'
WITH DISTINCT r, startNode(r) AS s, endNode(r) AS o
RETURN labels(s)[0] AS subject_label,
       coalesce(s.name, s.version, toString(s.number)) AS subject,
       type(r) AS predicate,
       coalesce(o.name, o.version, toString(o.number)) AS object,
       properties(r) AS props
ORDER BY subject_label, subject, predicate, object
"""

LABELS_SEEN = """
MATCH (e)-[:MENTIONED_IN]->(c:Chunk) WHERE c.id IN $ids
RETURN DISTINCT labels(e)[0] AS label
"""

COMPLETE_SET = """
MATCH (n) WHERE $label IN labels(n) AND n.demo = $demo
RETURN count(n) AS n,
       collect(coalesce(n.name, n.version, toString(n.number))) AS members
"""

# Types where an exhaustive list is meaningful in an answer. Feature and Chunk are
# excluded because dumping 11 long feature texts drowns the prompt.
CENSUS_LABELS = {"EntranceExam", "Programme", "School", "Facility", "CourseBasket",
                 "CouncilMeeting", "Regulation", "GoverningBody", "AdmissionCriterion"}

# Words in a question that name an entity TYPE. Asking "which schools..." should make
# the graph produce every School, whatever the retriever happened to return.
LABEL_WORDS = {
    "School": ["school", "schools"],
    "Facility": ["facility", "facilities", "lab", "labs", "studio", "studios"],
    "EntranceExam": ["exam", "exams", "examination", "examinations", "entrance test"],
    "Programme": ["programme", "programmes", "program", "programs", "degree", "degrees",
                  "course of study"],
    "CouncilMeeting": ["meeting", "meetings", "council"],
    "Regulation": ["regulation", "regulations", "version", "versions"],
    "CourseBasket": ["basket", "baskets"],
    "AdmissionCriterion": ["criterion", "criteria", "requirement", "requirements"],
    "GoverningBody": ["body", "bodies", "committee", "committees"],
}


def format_fact(record):
    """One graph fact as a line, including the edge properties.

    Single definition on purpose: an earlier version formatted facts separately in
    the ablation module, quietly dropped the properties there, and made the graph
    look as though it had lost information it actually held.

    The workshop strips the internal `demo` key with apoc.map.removeKeys inside the
    Cypher. This copy does it here in Python instead, so the query needs no APOC at
    all — Neo4j Aura ships only a subset of APOC, and depending on it is the kind of
    thing that works locally and fails once deployed.
    """
    props = {k: v for k, v in (record["props"] or {}).items()
             if v is not None and k != "demo"}
    detail = (" [" + "; ".join(f"{k}={v}" for k, v in sorted(props.items())) + "]"
              if props else "")
    return f"{record['subject']} -{record['predicate']}{detail}-> {record['object']}"


def labels_from_question(question):
    """Entity types the question is asking about, by surface word."""
    low = question.lower()
    return [label for label, words in LABEL_WORDS.items()
            if any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)]


def build_context(session, question, model, collection, k=4):
    hit = collection.query(query_embeddings=[embed_query(model, question)],
                           n_results=k, include=["documents", "metadatas"])
    ids, docs, metas = hit["ids"][0], hit["documents"][0], hit["metadatas"][0]

    passages = "\n\n".join(
        f"[{i}] ({m['citation']})\n{d}" for i, d, m in zip(ids, docs, metas))

    asked = labels_from_question(question)

    # Edge properties carry the curated nuggets - the `evidence` sentence on
    # EXEMPT_FROM, the `condition_group` that encodes (UCEED OR V-DAT) AND 10+2,
    # the `source_note` recording a typo in the source. An earlier version emitted
    # bare subject-predicate-object and silently dropped all of it, which threw away
    # the very facts that justify having a graph at all.
    facts = [format_fact(r)
             for r in session.run(NEIGHBOURHOOD, {"ids": ids, "labels": asked})]

    labels = [r["label"] for r in session.run(LABELS_SEEN, {"ids": ids})]
    census = []
    for label in sorted((set(labels) | set(asked)) & CENSUS_LABELS):
        row = session.run(COMPLETE_SET, {"label": label, "demo": DEMO}).single()
        census.append(f"ALL {label} in the document ({row['n']} total): "
                      + ", ".join(sorted(row["members"])))

    # Facts are NOT truncated arbitrarily. An earlier version kept facts[:60]; because
    # the list is sorted by label, that silently dropped every School -HAS_FACILITY->
    # triple and made the facilities question fail. If a cap is ever needed, rank by
    # relevance to the question rather than cutting the tail off an alphabetical list.
    context = (f"PASSAGES:\n{passages}\n\n"
               f"GRAPH FACTS:\n" + "\n".join(facts) + "\n\n"
               f"COMPLETE SETS:\n" + "\n".join(census))
    return ids, context, facts, census


def hybrid_rag(question, k=4, driver=None, database=None,
               model=None, collection=None, client=None, retries=6):
    model = model or get_model()
    collection = collection or get_collection()
    client = client or genai.Client(api_key=google_api_key())
    close = driver is None
    if driver is None:
        driver, database = get_driver()

    with driver.session(database=database) as session:
        ids, context, facts, census = build_context(session, question, model, collection, k)

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
    if close:
        driver.close()
    if text is None:
        return {"model": MODEL, "question": question, "retrieved": ids, "answer": "<rate limited>",
                "citations": [], "unverified": [], "n_facts": len(facts),
                "n_census": len(census)}

    answer, _, block = text.partition("SOURCES:")
    citations, unverified = [], []
    for line in block.strip().splitlines():
        if "|" not in line:
            continue
        cid, _, quote = line.partition("|")
        cid, quote = cid.strip().strip("[]"), quote.strip().strip('"')
        if cid.upper() == "GRAPH":
            citations.append({"chunk": "GRAPH", "citation": "knowledge graph", "quote": quote})
            continue
        chunk = _chunks.get(cid)
        if chunk and _normalise(quote) and _normalise(quote) in _normalise(chunk["text"]):
            citations.append({"chunk": cid, "citation": chunk["citation"], "quote": quote})
        else:
            unverified.append((cid, quote, "quote not found in that passage"))

    return {"model": MODEL, "question": question, "retrieved": ids, "answer": answer.strip(),
            "citations": citations, "unverified": unverified,
            "n_facts": len(facts), "n_census": len(census)}


def show(result):
    print(f"Q: {result['question']}")
    print(f"   retrieved: {result['retrieved']}")
    print(f"   context  : {result['n_facts']} graph facts, {result['n_census']} complete sets\n")
    print(f"   {result['answer']}\n")
    for c in result["citations"]:
        print(f"     [{c['citation']}]")
        print(f'       "{c["quote"][:110]}"')
    for cid, quote, reason in result["unverified"]:
        print(f"   !! UNVERIFIED [{cid}] - {reason}: \"{quote[:70]}\"")
