# Naive RAG vs KAG vs Hybrid RAG — the side-by-side demo

One question, three retrieval strategies, three panels. The point of the app is that
the strategies fail on **different questions**, and that is only convincing when you
can see all three answer the same question at the same moment.

This is a **standalone copy** of the pipeline in `../ffcs-kg-workshop`. It does not
import from the workshop and does not modify it; the two can be changed independently.

```
streamlit run app.py          →  http://localhost:8501
```

---

## What it shows

| Tab | Contents |
|---|---|
| **Compare** | One question, three panels. Naive RAG's retrieved chunks and similarity scores; KAG's Cypher, result rows and provenance; hybrid's complete sets and full assembled prompt. |
| **Context recall** | Did the evidence even reach the prompt? 9 probes × 3 strategies, measured with no API calls, charted. |
| **Corpus & graph** | The 18 chunks, and the 126-node / 266-edge graph they join to. |

The preset questions are grouped **by the failure they expose** — a counting question,
a prose question, one the document does not answer.

The measured result, which the chart makes obvious at a glance:

| | Local facts | Counting / lists | Prose & rationale | Total |
|---|:---:|:---:|:---:|:---:|
| Naive RAG | ✅ | ❌ | ✅ | **63%** |
| KAG | ✅ | ✅ | ❌ | **85%** |
| Hybrid | ✅ | ✅ | ✅ | **100%** |

> Top-k retrieval is a **sample** of the corpus, so it cannot answer questions about
> the whole corpus. An ontology is a **projection** of the text, so it cannot answer
> questions about what it did not model.

---

## Layout

```
├── app.py                    the three panels, the recall chart, the corpus view
├── requirements.txt          pinned; Community Cloud installs from this on every deploy
├── scripts/
│   └── load_graph.py         ONE-TIME: load the graph into Neo4j (local or Aura)
├── data/
│   └── chunks.json           18 chunks with page/passage citations
├── .streamlit/
│   └── secrets.toml.example  copy to secrets.toml and fill in
└── src/                      copied verbatim from the workshop, except where noted
    ├── config.py             paths + connection settings, read from the environment
    ├── build_vectorstore.py  chunks → Chroma
    ├── graph_data.py         the facts, transcribed from the document
    ├── build_graph.py        the facts → Neo4j
    ├── verify_graph.py       11 checks that the graph answers correctly
    ├── kag.py                the questions, written as Cypher
    ├── cited_rag.py          naive RAG with verified citations
    ├── hybrid_rag.py         the hybrid pipeline
    └── ablation.py           context recall, with no API calls
```

**One deliberate difference from the workshop.** `hybrid_rag.py` drops the internal
`demo` key in Python instead of calling `apoc.map.removeKeys` in Cypher. Neo4j Aura
ships only a subset of APOC, so depending on it is exactly the kind of thing that
works locally and fails once deployed. The facts produced are identical — the graph
still reaches 100% context recall, `condition_group` and `evidence` properties and all.

---

## Run it locally

You need a Neo4j with the graph loaded. The quickest is the workshop's:

```bash
cd ../ffcs-kg-workshop && docker compose up -d neo4j
```

Then, from this directory:

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill in the values
python scripts/load_graph.py                                  # one time
streamlit run app.py
```

The vector store is **not** a setup step — the app builds it on first run and caches
it for the life of the process.

---

## Deploy it free on Streamlit Community Cloud

Community Cloud runs `app.py` on a managed container. There is **no Docker and no
local database**, so Neo4j has to live somewhere else. Aura's free tier is the
straightforward option.

### 1. Create a free Neo4j Aura instance

1. Sign up at <https://console.neo4j.io> and create an instance (**AuraDB Free** is
   enough).
2. When it is created you are offered a credentials file **once** — download it. The
   password is never shown again.
3. **Copy all four values out of that file verbatim.** Do not assume them. The URI
   looks like `neo4j+s://xxxxxxxx.databases.neo4j.io`, and the `+s` matters — it is
   TLS, which Community Cloud requires. Username and database name are usually
   `neo4j`, but not always: some instances use the instance id (the subdomain of the
   URI) for both, and guessing produces an `AuthError` on the username or a
   `DatabaseNotFound` on the database, neither of which says which field is wrong.

### 2. Load the graph into it, once

From your machine, not from the cloud:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml    # paste the Aura values
python scripts/load_graph.py
```

This writes 126 nodes and 266 relationships and then prints the 11 verification
checks. Aura keeps the data, so redeploying the app never repeats this step.

Every node and edge is tagged `demo: 'ffcs_kg'`, and the loader's wipe step deletes
**only** nodes carrying that tag, so this is safe to run against a database that
already holds other work — a LangChain-built graph, an earlier experiment. Both
graphs coexist; the app reads only its own.

### 3. Get a Gemini API key

Free key at <https://aistudio.google.com/apikey>. Read step 6 before you use it.

### 4. Push to GitHub

Community Cloud deploys from a GitHub repo. This folder is already inside one.
**Do not commit `.streamlit/secrets.toml`** — it is in `.gitignore`, and it must stay
there. A key committed to a public repo stays in the git history after you delete the
line, and Google will usually revoke it before you notice.

### 5. Create the app

At <https://share.streamlit.io> → **Create app** → **Deploy a public app from GitHub**:

| Field | Value |
|---|---|
| Repository | `janakimeena/VAC2026` |
| Branch | `main` |
| Main file path | `Day 3/streamlit-app/app.py` |
| Python version | 3.12 (under **Advanced settings**) |

Then open **Advanced settings → Secrets** and paste the contents of your
`secrets.toml` — the same keys, TOML format:

```toml
NEO4J_URI = "neo4j+s://xxxxxxxx.databases.neo4j.io"
NEO4J_USERNAME = "…"        # from the credentials file — often "neo4j",
NEO4J_PASSWORD = "…"        #   sometimes the instance id
NEO4J_DATABASE = "…"        # likewise
GOOGLE_API_KEY = "…"
GEMINI_MODEL = "gemini-3-flash-preview"
```

Click **Deploy**. The first build takes several minutes — it installs torch and
downloads the embedding model.

> **If the main file path is rejected**, the space in `Day 3` is the likely cause.
> Either move this folder to a path without a space, or push it as its own repository
> with `app.py` at the root. Nothing in the app depends on where it sits.

### 6. Before you share the URL

**A public Community Cloud app is public.** Generation is on by default and every
visitor's questions spend *your* Gemini quota — the free tier is roughly 5 requests
per minute plus a small daily cap, so a handful of curious visitors can exhaust it
and leave the app rate-limited for your class. Pick one:

- **Restrict viewers.** In the app's settings → **Sharing**, limit access to invited
  email addresses. The app stays free; only people you invite can open it.
- **Leave the key out.** Deploy without `GOOGLE_API_KEY`. The app runs in
  retrieval-only mode and still demonstrates the whole argument — the *Context
  recall* tab needs no API calls at all, and the context comparison is where the
  three strategies actually differ.
- **Accept it** for a short-lived demo, and remove the key from Secrets afterwards.

---

## Known limits of the free tier

| | |
|---|---|
| **Aura Free pauses after 3 days idle** | The app will then show a connection error. Resume it from the Aura console; the data survives. This is the most common reason a working deployment stops working a week later. |
| **Memory** | Community Cloud gives roughly 1 GB. `sentence-transformers` pulls in torch, and this app sits inside that budget but not comfortably. If you hit an out-of-memory restart loop, the fix is to precompute the 18 chunk embeddings and drop torch entirely. |
| **Cold starts** | The app sleeps after inactivity. Waking it re-downloads the embedding model (~130 MB) and rebuilds the vector store, so the first question after a sleep is slow. Open it a few minutes before a class. |
| **Ephemeral disk** | Nothing written at runtime survives a restart. That is why the vector store is rebuilt rather than committed, and why the graph lives in Aura. |
