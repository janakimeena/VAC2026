# Knowledge Graphs, KAG and Hybrid RAG — a hands-on workshop

Build a knowledge graph and a vector store from the **same 3-page PDF**, then measure where
each one fails and why combining them helps.

Everything here was measured on this corpus, not assumed. Where the result contradicts the
usual textbook story about RAG, the notebooks say so.

---

## Quick start

```bash
git clone <this-repo>
cd ffcs-kg-workshop
cp .env.example .env          # optional: only needed for live LLM answers
docker compose up --build     # first build ~5 min, downloads the embedding model
```

Then, in a second terminal:

```bash
docker compose exec workshop ./setup.sh
```

That chunks the PDF, builds the graph, builds the vector store, and verifies all of it.

Open:

- **Jupyter** → http://localhost:8888 → `notebooks/`
- **Neo4j Browser** → http://localhost:7474 (user `neo4j`, password `ffcsdemo123`)

To stop: `docker compose down`. To also delete the graph: `docker compose down -v`.

### No API key needed

The graph, the vector store, the coverage test and the ablation all run **completely offline**.
Both notebooks open with answers recorded from real runs, so a whole class can work through
them with no API calls at all.

A key is only needed to *regenerate* answers live. The Gemini free tier is **5 requests/minute**
plus a small daily cap, so it is not suitable for a class sharing one key.

### Running without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD/src
docker run -d --name ffcs-neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/ffcsdemo123 -e NEO4J_PLUGINS='["apoc"]' neo4j:5-community
./setup.sh
```

APOC is required — `kg_coverage.py` and `hybrid_rag.py` use `apoc.convert.toJson` and
`apoc.map.removeKeys`.

---

## What you build

A knowledge graph of **126 nodes and 266 relationships** extracted from `data/small.pdf`
(an extract of the VIT FFCS Academic Regulations 4.0), alongside a Chroma vector store of the
same document, joined on a shared chunk id:

```
  Chroma          id = "chunk_p3_04"  ->  embedding, text, citation
                        |  same string
  Neo4j    (:Chunk {id: "chunk_p3_04"})  ->  MENTIONED_IN edges to entities
```

That join is what makes hybrid retrieval possible, and it is why the graph can cite a page.

---

## The headline result

Measured on 18 questions, one document, the same LLM throughout:

| Question type | Naive RAG | Knowledge graph | Hybrid |
|---|:---:|:---:|:---:|
| Local facts (negation, OR/AND logic, absence) | correct | correct | correct |
| Global aggregates (counts, exhaustive lists) | **wrong** | correct | correct |
| Unmodelled prose (rationale, objectives, description) | correct | **no data** | correct |

Neither pure approach wins. They fail in **opposite directions**:

> Top-k retrieval is a **sample** of the corpus, so it cannot answer questions about the whole
> corpus. An ontology is a **projection** of the text, so it cannot answer questions about what
> it did not model.

Context recall — does the evidence even reach the prompt? — measured with no API calls:

| | Local | Global | Prose | Total | Context size |
|---|:---:|:---:|:---:|:---:|---|
| passages only | 2/2 | 11/21 | 4/4 | **63%** | 2,337 chars |
| graph only | 2/2 | 21/21 | **0/4** | **85%** | 3,611 chars |
| hybrid | 2/2 | 21/21 | 4/4 | **100%** | 5,951 chars |

Hybrid reaches 100% — at **2.5× the prompt size**. That is the trade, and it is not free.

---

## Repository layout

```
├── data/                 the corpus, chunks, and recorded LLM answers
│   ├── small.pdf                 3-page source document
│   ├── chunks.json               18 chunks with page/passage citations
│   ├── naive_rag_results.json    verbatim answers from live runs
│   └── hybrid_results.json
├── notebooks/
│   ├── 1_naive_rag_vs_knowledge_graph.ipynb
│   └── 2_hybrid_rag.ipynb
└── src/
    ├── config.py                 paths and connection settings (start here)
    ├── chunk_pdf.py              PDF -> 18 chunks
    ├── add_citations.py          page/passage citations into both stores
    ├── graph_data.py             the facts, transcribed from the document
    ├── build_graph.py            the facts -> Neo4j
    ├── verify_graph.py           11 checks that the graph answers correctly
    ├── build_vectorstore.py      chunks -> Chroma
    ├── vector_search.py          pure vector retrieval baseline
    ├── kag.py                    the questions, written as Cypher
    ├── cited_rag.py              naive RAG with verified citations
    ├── kg_coverage.py            fair proof of what the graph does NOT contain
    ├── hybrid_rag.py             the hybrid pipeline
    └── ablation.py               context recall, with no API calls
```

`graph_data.py` and `build_graph.py` are deliberately separate: one is *what the graph says*,
the other is *how it gets loaded*. You can read the facts without reading any Cypher.

---

## Suggested order

1. **`data/small.pdf`** — read it. Find its three defects: it is truncated mid-sentence, it
   contains a typo, and one date is left as `xxxxxxxxxxxxxxx`. All three matter later.
2. **Design an ontology on paper first** — entity types, relationships, properties. What are
   the things in this document, and how do they relate? Do this before reading any code.
   Then read `src/graph_data.py`, which is one worked answer, and argue with it.
3. **`src/chunk_pdf.py` → `src/build_graph.py` → `src/verify_graph.py`** — build it.
4. **Neo4j Browser** — explore what you built. Start with the schema itself:
   ```cypher
   CALL db.schema.visualization()
   ```
   then the interesting patterns:
   ```cypher
   MATCH (p:Programme)-[r:ADMITS_VIA|EXEMPT_FROM]->(x:EntranceExam) RETURN p, r, x;
   MATCH (b:Programme {name:'B.Des'})-[r:REQUIRES]->(c)
   RETURN b.name, r.condition_group, c.name;
   ```
   (Use `RETURN c.id, c.page, c.text` on `:Chunk` nodes — `RETURN c` dumps a 384-float vector.)
5. **`notebooks/1_...`** — where each approach fails, and why.
6. **`notebooks/2_...`** — hybrid, built one stage at a time.

---

## Three things worth knowing before you start

**The corpus is 3 pages.** The whole document fits in one prompt, so retrieval is nearly solved
at this scale. That sharpens the lesson rather than weakening it: the graph's advantage here is
**completeness and curation, not recall**.

**Naive RAG is not as broken as tutorials claim.** It answered 10 of 18 questions correctly here,
including the negation, OR/AND-logic and missing-information cases usually cited as its
weaknesses. The real failures are aggregate questions, and they have a precise cause.

**The graph is right about one question because a human fixed a typo.** That is a genuine
advantage — a knowledge graph is where curation lives and can be audited — but it is not magic,
and it is not free.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `ServiceUnavailable` connecting to Neo4j | container still starting — compose waits for the healthcheck, but a manual `docker run` needs ~20 s |
| `Unknown function 'apoc.convert.toJson'` | APOC plugin missing; recreate the Neo4j container with `NEO4J_PLUGINS='["apoc"]'` |
| `RuntimeError: GOOGLE_API_KEY is not set` | only live cells need it; the recorded answers work without |
| `429 RESOURCE_EXHAUSTED` | free-tier limit — 5 requests/minute, small daily cap. Try another `GEMINI_MODEL` |
| Notebook can't import `kag` | run it from `notebooks/`; the first cell puts `src/` on the path |
| `Bind for 0.0.0.0:8888 failed: port is already allocated` | something else uses that port. `JUPYTER_PORT=8899 docker compose up` (also `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT`) |
| Graph looks empty | run `./setup.sh` |
| Files in `data/` owned by `root`, cannot delete (Linux) | the container ran as root. Set `DOCKER_UID=$(id -u) DOCKER_GID=$(id -g)` in `.env`, then `docker compose up --build`. To clear existing root-owned files: `docker run --rm -v "$PWD:/w" alpine rm -rf /w/data/chroma_ffcs` |

---

## Publishing this to GitHub

The folder is self-contained — no absolute paths, no credentials, no dependency on where it
sits on disk. To publish:

```bash
cp -r ffcs-kg-workshop ~/somewhere-else      # or just move it
cd ~/somewhere-else/ffcs-kg-workshop
rm -rf data/chroma_ffcs src/__pycache__ .ipynb_checkpoints notebooks/.ipynb_checkpoints

git init
git add -A                                   # .gitignore keeps .env and build output out
git commit -m "Knowledge graph, KAG and hybrid RAG workshop"
git branch -M main
git remote add origin git@github.com:<you>/<repo>.git
git push -u origin main
```

That commits **29 files, about 900 KB**. The vector store is rebuilt by `setup.sh`, so it is
deliberately not committed.

**Check before you push:** `.env` must not appear in `git status`. It is gitignored, but a key
pushed once is a key that must be rotated.

The notebooks are committed **with their outputs**, on purpose: students can read the whole
argument before running anything, and the recorded LLM answers are the evidence the notebooks
discuss. If you would rather commit clean notebooks, strip outputs with
`jupyter nbconvert --clear-output --inplace notebooks/*.ipynb` — but then everyone needs an API
key to see the results.
