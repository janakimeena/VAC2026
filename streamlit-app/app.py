"""Streamlit demo: the same question answered three ways.

    streamlit run app.py

Three retrieval strategies run side by side on the same corpus, so a class can
watch them succeed and fail on the SAME question rather than reading three
separate notebook outputs:

    Naive RAG   embed the question, take the top-k chunks, answer from the text
    KAG         answer by traversing the graph - the answer is a path, not a lookup
    Hybrid      passages for prose, graph facts and complete sets for structure

Nothing here reimplements retrieval. Every panel calls the same module the
workshop notebooks call, so what is on screen is the code the students read:

    cited_rag.cited_rag()   hybrid_rag.hybrid_rag()   kag.QUERIES   ablation.run()

DEPLOYMENT
----------
This is a standalone copy of the Day 3/ffcs-kg-workshop pipeline, packaged to run on
Streamlit Community Cloud, where there is no Docker and no local database. Two
things therefore differ from the workshop:

  * Neo4j lives elsewhere. Point NEO4J_URI at an Aura instance (or any reachable
    Neo4j) and load it once with `python scripts/load_graph.py`.
  * The vector store is rebuilt on cold start. Community Cloud's filesystem is
    ephemeral, so Chroma is built into a temp directory the first time the app
    runs and cached for the life of the process. 18 chunks, a few seconds.

Credentials come from st.secrets (Community Cloud) or the environment (local),
in that order. See README.md.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

# Secrets -> environment, BEFORE config is imported.
#
# config.py is a verbatim copy of the workshop's, and reads os.environ. Bridging
# here rather than editing it keeps the two files identical, so a student can diff
# the deployed app against the workshop and find no divergence in the code that
# matters. Streamlit raises if no secrets file exists at all, hence the guard.
SECRET_KEYS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE",
               "GOOGLE_API_KEY", "GEMINI_MODEL")

# What the bridge actually found, recorded so a failure can say WHICH keys arrived
# rather than leaving the reader to guess. Swallowing the error and reporting only
# the downstream symptom — a connection refused against the default localhost URI —
# is what made this hard to diagnose the first time: the message named a URI nobody
# had configured, which reads like a wrong value rather than a missing one.
SECRETS_FOUND, SECRETS_ERROR = [], None
try:
    for _key in SECRET_KEYS:
        if _key in st.secrets and str(st.secrets[_key]).strip():
            os.environ[_key] = str(st.secrets[_key])
            SECRETS_FOUND.append(_key)
except Exception as _e:                     # no secrets configured at all
    SECRETS_ERROR = f"{type(_e).__name__}: {_e}"

# Chroma needs sqlite3 >= 3.35, and some managed images still ship an older one.
# pysqlite3-binary is a drop-in; swapping it into sys.modules before chromadb is
# imported is the standard Community Cloud fix. Harmless where sqlite is already
# new enough, because the import simply fails and we keep the stdlib module.
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import altair as alt
import pandas as pd

import ablation
import kag
from build_vectorstore import embed_query, get_collection, get_model
from config import (CHUNKS_JSON, DEMO, EMBEDDING_MODEL, GEMINI_MODEL, get_driver)

st.set_page_config(page_title="RAG vs KAG vs Hybrid", page_icon="🔍", layout="wide")

# Categorical slots 1-3 of the validated palette. Fixed per strategy, never per
# rank, so a strategy keeps its colour everywhere in the app.
COLOR = {"Naive RAG": "#2a78d6", "KAG": "#eb6834", "Hybrid RAG": "#1baf7a"}

BLURB = {
    "Naive RAG": "Embed the question, take the top-k chunks, answer from their text.",
    "KAG": "Answer by traversing the graph. The answer is a path, not a text match.",
    "Hybrid RAG": "Passages for prose, graph facts and complete sets for structure.",
}

# Questions worth asking in class, grouped by what they expose. The label says what
# the question is FOR, which is the part that gets lost when a demo is just a textbox.
PRESETS = {
    "Local fact — both should get this": [
        "Which entrance exam must a B.Tech Fashion Technology applicant take?",
        "What do I need to get into B.Des?",
    ],
    "Counting / exhaustive list — naive RAG breaks here": [
        "How many distinct entrance examinations are named in the document? List them.",
        "Which schools are named in the document?",
        "List all the facilities at the school that offers B.Des.",
        "How many Academic Council meetings are referenced in the document?",
    ],
    "Prose and rationale — KAG breaks here": [
        "What do employers expect from students?",
        "What is the main objective of the design programmes at V-SIGN?",
    ],
    "Not in the document — everything should refuse": [
        "How is a student admitted to M.Des?",
    ],
    "Multi-hop across chunks": [
        "Which regulation version does 4.0 replace and when was it approved?",
        "Which facilities belong to the school that offers B.Des?",
    ],
}


# ---------------------------------------------------------------- resources

@st.cache_resource(show_spinner="Loading the embedding model…")
def load_model():
    return get_model()


@st.cache_resource(show_spinner="Building the vector store (first run only)…")
def load_collection():
    """Open the Chroma collection, building it if this process has never seen one.

    On Community Cloud the filesystem is ephemeral and starts empty, so there is
    nothing to open on a cold start. Building it here — rather than asking the
    operator to run a script they cannot run on a managed host — is what makes the
    app deployable. It is 18 chunks; the cost is a few seconds, once per process.

    Existence is checked BEFORE opening, which matters more than it looks. Calling
    get_collection() on an empty path does not fail cleanly: it creates the store
    and registers a client for that path in Chroma's process-wide cache. The
    rebuild then deletes the directory out from under that cached client, and every
    subsequent write fails with "attempt to write a readonly database". Clearing
    the cache before a rebuild is the belt to that braces.
    """
    import build_vectorstore
    from config import CHROMA_DIR

    def rebuild():
        try:
            from chromadb.api.shared_system_client import SharedSystemClient
            SharedSystemClient.clear_system_cache()
        except Exception:
            pass
        build_vectorstore.main()

    if not CHROMA_DIR.exists():
        rebuild()
    try:
        return get_collection()
    except Exception:
        rebuild()                       # present but empty, partial or stale
        return get_collection()


@st.cache_resource(show_spinner="Connecting to Neo4j…")
def load_driver():
    return get_driver()


def have_key():
    import os
    return bool(os.environ.get("GOOGLE_API_KEY"))


def preflight():
    """Fail loudly and usefully, rather than throwing a stack trace at a class."""
    problems = []
    if not CHUNKS_JSON.exists():
        problems.append(f"No chunks at `{CHUNKS_JSON}` — run `python src/chunk_pdf.py`.")
    try:
        driver, db = load_driver()
        with driver.session(database=db) as s:
            n = s.run("MATCH (n {demo: $d}) RETURN count(n) AS n", {"d": DEMO}).single()["n"]
        if n == 0:
            problems.append("Neo4j is reachable but holds no graph — load it once with "
                        "`python scripts/load_graph.py`.")
    except Exception as e:
        uri = os.environ.get("NEO4J_URI")
        if not uri:
            # No URI anywhere. The connection error is a red herring — the real
            # fault is upstream, in configuration that never arrived.
            detail = ["**`NEO4J_URI` is not set**, so the app fell back to "
                      "`bolt://localhost:7687`, where nothing is listening.",
                      "",
                      f"Secrets keys found: "
                      f"{', '.join(f'`{k}`' for k in SECRETS_FOUND) or '_none_'}."]
            if SECRETS_ERROR:
                detail.append(f"Reading secrets failed with `{SECRETS_ERROR}` — on "
                              "Community Cloud that means no Secrets have been saved "
                              "for this app; locally it means there is no "
                              "`.streamlit/secrets.toml`.")
            detail += [
                "",
                "In the app's **Settings → Secrets**, paste the keys at the **top "
                "level** of the TOML — not underneath a `[section]` header, which "
                "would nest them where this lookup cannot see them:",
                "```toml",
                'NEO4J_URI = "neo4j+s://xxxxxxxx.databases.neo4j.io"',
                'NEO4J_USERNAME = "…"',
                'NEO4J_PASSWORD = "…"',
                'NEO4J_DATABASE = "…"',
                "```",
                "Saving Secrets restarts the app on its own; if nothing changes, "
                "reboot it once.",
            ]
            problems.append("\n".join(detail))
        else:
            problems.append(
                f"Cannot reach Neo4j at `{uri}` ({type(e).__name__}). "
                f"Secrets keys found: "
                f"{', '.join(f'`{k}`' for k in SECRETS_FOUND) or '_none_'}. "
                "Check the username, password and database name — an `AuthError` means "
                "the username or password, a `DatabaseNotFound` means the database "
                "name, and neither is always `neo4j`. An Aura instance left idle for "
                "days may simply be paused; resume it from the Aura console.")
    return problems


# ---------------------------------------------------------------- KAG routing

@st.cache_data(show_spinner=False)
def kag_question_vectors():
    """Embed the canned KAG questions once, so a free-text question can be routed."""
    model = load_model()
    keys = list(kag.QUERIES)
    return keys, [embed_query(model, kag.QUERIES[k][0]) for k in keys]


def route_to_cypher(question):
    """Pick the canned Cypher whose question is closest to the one asked.

    A production KAG system has an LLM write Cypher from the schema. Here the
    queries are written out by hand so the mechanism stays visible and the demo is
    deterministic — which means an arbitrary question has to be ROUTED to one of
    them. The similarity is shown in the UI, and a weak match is called out,
    because "the graph has no query for this" is itself one of KAG's real failure
    modes and hiding it would misrepresent the method.
    """
    keys, vectors = kag_question_vectors()
    q = embed_query(load_model(), question)
    scores = [(sum(a * b for a, b in zip(q, v)), k) for v, k in zip(vectors, keys)]
    score, key = max(scores)
    return key, score


# ---------------------------------------------------------------- panels

def panel_header(name, extra=""):
    st.markdown(
        f"<div style='border-left:4px solid {COLOR[name]};padding-left:.6rem;margin-bottom:.4rem'>"
        f"<strong>{name}</strong><br>"
        f"<span style='font-size:.82rem;opacity:.75'>{BLURB[name]}{extra}</span></div>",
        unsafe_allow_html=True)


def show_citations(result):
    for c in result["citations"]:
        tag = c.get("citation", "knowledge graph")
        st.markdown(f"<span style='font-size:.8rem;opacity:.7'>[{tag}]</span>",
                    unsafe_allow_html=True)
        st.markdown(f"> {c['quote'][:200]}")
    for cid, quote, reason in result["unverified"]:
        st.warning(f"UNVERIFIED [{cid}] — {reason}\n\n\"{quote[:120]}\"", icon="⚠️")


def run_naive(question, k, generate):
    model, collection = load_model(), load_collection()
    hit = collection.query(query_embeddings=[embed_query(model, question)],
                           n_results=k, include=["documents", "metadatas", "distances"])
    ids, docs = hit["ids"][0], hit["documents"][0]
    metas, dists = hit["metadatas"][0], hit["distances"][0]

    panel_header("Naive RAG", f" · top-{k}")
    if generate:
        from cited_rag import cited_rag
        with st.spinner("Generating…"):
            result = cited_rag(question, k=k, model=model, collection=collection)
        st.markdown(result["answer"] or "_(no answer)_")
        show_citations(result)

    # The compact summary stays visible in every panel so the three columns can be
    # read against each other at a glance. The bulk goes in a collapsed expander:
    # an expanded dump of four passages makes this column ten times taller than the
    # other two and destroys the side-by-side comparison the app exists for.
    st.markdown(f"**Retrieved {len(ids)} of 18 chunks**")
    for rank, (cid, meta, dist) in enumerate(zip(ids, metas, dists), 1):
        st.markdown(f"<div style='font-size:.82rem'>{rank}. <code>{cid}</code> · "
                    f"{meta['citation']} · sim {1 - dist:.3f}</div>", unsafe_allow_html=True)
    with st.expander("Passage text"):
        for cid, doc, meta in zip(ids, docs, metas):
            st.markdown(f"**`{cid}`** · {meta['citation']}")
            st.caption(doc)
    st.caption(f"{sum(len(d) for d in docs):,} characters of prose — a **sample** of the "
               f"corpus, which is why counting questions fail here.")


def run_kag(question, generate):
    key, score = route_to_cypher(question)
    canned, cypher = kag.QUERIES[key]
    panel_header("KAG", f" · query <code>{key}</code>")

    if score < 0.80:
        st.warning(f"No close graph query for this question (best match {score:.2f}). "
                   "The ontology does not model it — a genuine KAG failure mode.", icon="⚠️")

    driver, db = load_driver()
    with driver.session(database=db) as session:
        rows = [dict(r) for r in session.run(cypher, {"demo": DEMO})]
        prov = kag.provenance(session, key)

    st.markdown(f"**Traversal result**")
    if rows:
        for row in rows:
            for field, value in row.items():
                st.markdown(f"<div style='font-size:.82rem'><strong>{field}</strong> — "
                            f"{value}</div>", unsafe_allow_html=True)
    else:
        st.info("The traversal returned nothing. The graph holds no such path.")

    with st.expander("Cypher"):
        st.caption(f"Routed to: _{canned}_  (similarity {score:.2f})")
        st.code(cypher.strip(), language="cypher")
    if prov:
        st.caption("Provenance: " + ", ".join(f"`{p['chunk']}`" for p in prov))
    st.caption("An exact traversal — a **census**, not a sample. No text is read at all, "
               "which is why prose questions have nothing to return.")


def run_hybrid(question, k, generate):
    from hybrid_rag import build_context, hybrid_rag

    model, collection = load_model(), load_collection()
    driver, db = load_driver()
    panel_header("Hybrid RAG", f" · top-{k} + graph")

    # Built here whether or not we generate, so the expander can always show the
    # class the exact three blocks that go into the prompt. That context IS the
    # lesson; the generated sentence is just what an LLM did with it.
    with driver.session(database=db) as session:
        ids, context, facts, census = build_context(session, question, model, collection, k)

    if generate:
        with st.spinner("Generating…"):
            result = hybrid_rag(question, k=k, driver=driver, database=db,
                                model=model, collection=collection)
        st.markdown(result["answer"] or "_(no answer)_")
        show_citations(result)

    st.markdown(f"**{len(ids)} passages + {len(facts)} graph facts + "
                f"{len(census)} complete sets**")
    # The complete sets are the block that repairs the counting failures, so they
    # are the part shown without a click.
    for line in census:
        st.markdown(f"<div style='font-size:.82rem'>{line}</div>", unsafe_allow_html=True)
    if not census:
        st.caption("_No complete sets apply to this question — hybrid falls back to "
                   "passages plus 1-hop facts._")
    with st.expander("Full assembled prompt"):
        st.code(context, language="text")
    st.caption(f"{len(context):,} characters — prose **and** structure. The larger prompt "
               f"is the price of covering both failure modes.")


# ---------------------------------------------------------------- tabs

def tab_compare():
    left, right = st.columns([3, 1])
    with left:
        group = st.selectbox("Question type", list(PRESETS),
                             help="Each group targets a different failure mode.")
        question = st.selectbox("Question", PRESETS[group] + ["— type my own —"])
        if question == "— type my own —":
            question = st.text_input("Your question", "Which schools are named in the document?")
    with right:
        k = st.slider("top-k", 1, 8, 4, help="Chunks the retriever returns. "
                                             "The corpus has 18 in total.")
        generate = st.toggle("Generate answers", value=have_key(), disabled=not have_key(),
                             help="Calls Gemini for each panel. Turn it off to compare the "
                                  "assembled context alone — which is where the three "
                                  "strategies actually differ, and costs no quota.")
    if not have_key():
        st.info("No `GOOGLE_API_KEY` configured — running in retrieval-only mode. The panels "
                "below show what each strategy puts in front of the LLM, which is where they "
                "actually differ.", icon="ℹ️")

    if not question.strip():
        return
    st.divider()
    a, b, c = st.columns(3, gap="medium")
    with a:
        run_naive(question, k, generate)
    with b:
        run_kag(question, generate)
    with c:
        run_hybrid(question, k, generate)


@st.cache_data(show_spinner="Assembling 27 contexts…")
def recall_table(k):
    driver, db = load_driver()
    with driver.session(database=db) as session:
        rows = ablation.run(session, model=load_model(), collection=load_collection(), k=k)
    label = {"passages": "Naive RAG", "graph": "KAG", "hybrid": "Hybrid RAG"}
    records = []
    for r in rows:
        for variant, name in label.items():
            records.append({
                "id": r["id"], "question": r["question"], "kind": r["kind"],
                "Strategy": name, "met": r[variant], "required": r["required"],
                "recall": r[variant] / r["required"],
                "missing": ", ".join(r[variant + "_missing"]) or "—",
                "chars": r[variant + "_chars"],
            })
    return pd.DataFrame(records)


def tab_recall():
    st.markdown("#### Did the evidence even reach the prompt?")
    st.caption("An answer can only be right if the facts it needs were in the context. "
               "This measures that directly — no API calls, no LLM, nothing to rate-limit. "
               "It separates *the evidence never arrived* from *the model misread it*.")
    k = st.slider("top-k", 1, 8, 4, key="recall_k")
    df = recall_table(k)

    order = ["Naive RAG", "KAG", "Hybrid RAG"]
    overall = df.groupby("Strategy")[["met", "required"]].sum()
    cols = st.columns(3)
    for col, name in zip(cols, order):
        met, req = overall.loc[name, "met"], overall.loc[name, "required"]
        col.metric(name, f"{met / req:.0%}", f"{met} of {req} facts", delta_color="off")

    st.markdown("###### Recall per question")
    base = alt.Chart(df).encode(
        x=alt.X("id:N", title=None, sort=list(df["id"].unique()),
                axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("Strategy:N", sort=order),
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white",
                         strokeWidth=2).encode(
        y=alt.Y("recall:Q", title="context recall", axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("Strategy:N", sort=order,
                        scale=alt.Scale(domain=order, range=[COLOR[s] for s in order]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["Strategy", "question", alt.Tooltip("recall:Q", format=".0%"),
                 "met", "required", "missing"],
    )
    # Label only the bars that fall short. Numbering every bar collides three labels
    # on every full-height group and says nothing — the shortfalls are the finding,
    # so those are what get named. Full identity is still available in the legend,
    # the tooltip and the table view below.
    labels = base.mark_text(dy=-6, fontSize=10, color="#52514e").transform_filter(
        alt.datum.recall < 1
    ).encode(
        y=alt.Y("recall:Q"),
        text=alt.Text("recall:Q", format=".0%"),
    )
    st.altair_chart((bars + labels).properties(height=300), width='stretch')

    kinds = df.drop_duplicates("id").set_index("id")["kind"].to_dict()
    st.caption("  ·  ".join(f"`{i}` {k}" for i, k in kinds.items()))
    st.markdown(
        "- **local** — one fact in one chunk. Retrieval finds it; so does the graph.\n"
        "- **global** — a count or an exhaustive list. Top-k is a *sample*, so naive "
        "RAG cannot answer it however good the embeddings are.\n"
        "- **prose** — rationale and objectives. Never modelled as entities, so the "
        "graph alone has nothing to say."
    )
    with st.expander("Table view"):
        st.dataframe(
            df.pivot(index=["id", "kind", "question"], columns="Strategy", values="recall")
              .reindex(columns=order).style.format("{:.0%}"),
            width='stretch')


def tab_corpus():
    import json
    driver, db = load_driver()
    with driver.session(database=db) as session:
        nodes = [dict(r) for r in session.run(
            "MATCH (n {demo: $d}) RETURN labels(n)[0] AS label, count(*) AS n "
            "ORDER BY n DESC", {"d": DEMO})]
        edges = [dict(r) for r in session.run(
            "MATCH ()-[r {demo: $d}]->() RETURN type(r) AS type, count(*) AS n "
            "ORDER BY n DESC", {"d": DEMO})]
    chunks = json.loads(CHUNKS_JSON.read_text())["chunks"]

    a, b, c = st.columns(3)
    a.metric("Chunks", len(chunks))
    b.metric("Graph nodes", sum(r["n"] for r in nodes))
    c.metric("Graph edges", sum(r["n"] for r in edges))
    st.caption("Both stores are keyed on the same chunk id. That join *is* hybrid RAG.")

    left, right = st.columns(2)
    left.markdown("###### Node labels")
    left.dataframe(pd.DataFrame(nodes), width='stretch', hide_index=True)
    right.markdown("###### Relationship types")
    right.dataframe(pd.DataFrame(edges), width='stretch', hide_index=True)

    with st.expander(f"The corpus — {len(chunks)} chunks from small.pdf"):
        for ch in chunks:
            st.markdown(f"**`{ch['id']}`** · {ch.get('citation', '')}")
            st.caption(ch["text"][:300] + ("…" if len(ch["text"]) > 300 else ""))


# ---------------------------------------------------------------- main

st.title("Naive RAG vs KAG vs Hybrid RAG")
st.caption("The same question, the same corpus, three retrieval strategies — "
           "so the failures line up side by side.")

problems = preflight()
if problems:
    st.error("Setup incomplete:\n\n" + "\n".join(f"- {p}" for p in problems))
    st.stop()

with st.sidebar:
    st.markdown("### Setup")
    st.write(f"Embedding: `{EMBEDDING_MODEL}`")
    st.write(f"Generation: `{GEMINI_MODEL}`" if have_key() else "Generation: _disabled_")
    st.write(f"Vector store: `{load_collection().count()}` chunks")
    st.markdown("---")
    st.markdown(
        "**The claim being tested**\n\n"
        "Naive RAG and KAG fail in *opposite* directions:\n\n"
        "- top-k is a sample, so RAG cannot count or enumerate\n"
        "- the ontology is a lossy projection, so KAG loses rationale and nuance\n\n"
        "Hybrid gives the model both, joined on the chunk id.")

compare, recall, corpus = st.tabs(["Compare", "Context recall", "Corpus & graph"])
with compare:
    tab_compare()
with recall:
    tab_recall()
with corpus:
    tab_corpus()
