# Knowledge Graphs, KAG and Hybrid RAG — a hands-on workshop

Build a knowledge graph and a vector store from the **same 3-page PDF**, then measure where
each one fails and why combining them helps.

Everything here was measured on this corpus, not assumed. Where the result contradicts the
usual textbook story about RAG, the notebooks say so.

---

## Setup

You need **Docker Desktop** (Windows/Mac) or **Docker Engine + compose** (Linux). Nothing else —
no Python install, no API key. Allow about 10 minutes for the first run, most of it the image build.

### 1. Get the code

```bash
git clone <this-repo>
cd ffcs-kg-workshop
```

### 2. Start the two containers

```bash
docker compose up --build
```

This builds the workshop image (~5 min the first time; it bakes in the 130 MB embedding model so
the classroom never waits on wifi) and starts Neo4j alongside it. **Leave this terminal running** —
it is the server. You will see Jupyter's startup banner when it is ready.

Linux only: run the container as yourself first, so files it writes belong to you —
`echo "DOCKER_UID=$(id -u)"$'\n'"DOCKER_GID=$(id -g)" >> .env`

### 3. Build the graph and the vector store

In a **second** terminal, in the same folder:

```bash
docker compose exec workshop ./setup.sh
```

This chunks the PDF, adds citations, loads the graph, builds the vector store, and then checks
its own work. It takes about a minute. **Wait for it to print `Ready.`** — the run ends with:

```
==> verifying everything the notebooks need
  PASS  chunks + citations     18/18 chunks carry a citation
  PASS  vector store           18 vectors in collection 'ffcs_chunks'
  PASS  knowledge graph        126 nodes, 266 relationships

Ready.
```

If you see a `FAIL` line instead, it names the one command that fixes it. The script is safe to
re-run as often as you like.

### 4. Open the notebooks

- **Jupyter** → http://localhost:8888 → `notebooks/` → start with `1_naive_rag_vs_knowledge_graph.ipynb`
- **Neo4j Browser** → http://localhost:7474 — user `neo4j`, password `ffcsdemo123`

Run the notebook cells **in order from the top**. The first cell loads the data every later cell
uses, so a kernel restart means starting from cell 1 again.

### Checking, stopping, restarting

```bash
docker compose exec workshop ./setup.sh --check   # is my build still complete?
docker compose down                               # stop; the graph survives
docker compose down -v                            # stop and delete the graph too
docker compose up                                 # start again (no --build needed)
```

`--check` verifies the three things the notebooks open — the chunk file, the vector store and the
graph — without rebuilding anything. Run it first whenever a notebook cell misbehaves.

### Windows notes

Use **PowerShell** and run the commands exactly as written above; `docker compose exec` runs them
inside Linux, so forward slashes are correct even on Windows.

Two things go wrong on Windows specifically, and both are worth knowing before they happen:

- **Line endings.** Git for Windows rewrites files to CRLF on checkout, which breaks `setup.sh`
  with `bad interpreter` or `$'\r': command not found`. The committed `.gitattributes` prevents
  this, so a fresh clone is fine. If you cloned before that file existed, re-clone or run
  `git config core.autocrlf false` and clone again.
- **`./setup.sh` must be run through `docker compose exec`**, not in PowerShell directly.
  PowerShell has no `bash`, and the scripts expect the container's Python and its Neo4j hostname.

### No API key needed

The graph, the vector store, the coverage test and the ablation all run **completely offline**.
Both notebooks open with answers recorded from real runs, so a whole class can work through
them with no API calls at all.

A key is only needed to *regenerate* answers live. Copy `.env.example` to `.env` and add one from
https://aistudio.google.com/apikey. The Gemini free tier is **5 requests/minute** plus a small
daily cap, so it is not suitable for a class sharing one key.

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

### What setup.sh actually does

Worth reading once, because the four steps are **not independent**:

```
  1  chunk_pdf.py         small.pdf   ->  data/chunks.json        (18 chunks)
  2  add_citations.py     chunks.json ->  + page/passage citations, pushed to both stores
  3  build_graph.py       graph_data.py -> Neo4j                  (126 nodes, 266 rels)
  4  build_vectorstore.py chunks.json ->  data/chroma_ffcs/       (18 vectors, 384 dims)
```

Step 1 rewrites `chunks.json` **without** citations and step 2 puts them back, so a run that
stops between the two leaves the notebooks half-working — the graph loads, but the citation
cells raise `KeyError: 'citation'`. This is why `setup.sh` verifies itself at the end rather
than assuming every step ran, and why the fix for almost anything odd is simply to run it again.

`data/chroma_ffcs/` is deliberately **not** committed (see `.gitignore`) — it is build output,
rebuilt by step 4. A fresh clone therefore has no vector store until you run `setup.sh`.

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
├── setup.sh              builds everything, then verifies it (--check to verify only)
├── docker-compose.yml    the two containers: Neo4j, and the workshop environment
├── data/                 the corpus, chunks, and recorded LLM answers
│   ├── small.pdf                 3-page source document
│   ├── chunks.json               18 chunks with page/passage citations
│   ├── naive_rag_results.json    verbatim answers from live runs
│   ├── hybrid_results.json
│   └── chroma_ffcs/              build output - created by setup.sh, not committed
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

**Try this first.** Most notebook errors are a missing build step, not a bug:

```bash
docker compose exec workshop ./setup.sh --check
```

Any `FAIL` line names the single command that fixes it. If everything passes, the problem is
elsewhere — look for your symptom below.

| Symptom | Cause and fix |
|---|---|
| `NotFoundError: Collection [ffcs_chunks] does not exist` | the vector store was never built — it is build output and is not in the repo. `docker compose exec workshop python src/build_vectorstore.py`, then restart the notebook kernel |
| `KeyError: 'citation'` in a notebook cell | `setup.sh` stopped between step 1 and step 2, so `chunks.json` was regenerated without citations. `docker compose exec workshop python src/add_citations.py`, then restart the kernel |
| `NameError` on `chunks`, `by_id`, `naive_gaps`, `collection`, `driver` | cells were run out of order, or the kernel was restarted. Re-run from the first cell |
| `bad interpreter: /usr/bin/env` or `$'\r': command not found` (Windows) | `setup.sh` was checked out with CRLF line endings. `.gitattributes` prevents this — re-clone, or `git config core.autocrlf false` then clone again |
| `ServiceUnavailable` connecting to Neo4j | container still starting — compose waits for the healthcheck, but a manual `docker run` needs ~20 s. `setup.sh` now waits up to 60 s on its own |
| `Unknown function 'apoc.convert.toJson'` | APOC plugin missing; recreate the Neo4j container with `NEO4J_PLUGINS='["apoc"]'` |
| `RuntimeError: GOOGLE_API_KEY is not set` | only live-answer cells need it; the recorded answers work without. Copy `.env.example` to `.env` to add one |
| `429 RESOURCE_EXHAUSTED` | free-tier limit — 5 requests/minute, small daily cap. Try another `GEMINI_MODEL` in `.env` |
| Notebook can't import `kag` | run it from `notebooks/`; the first cell puts `src/` on the path |
| `Bind for 0.0.0.0:8888 failed: port is already allocated` | something else uses that port. `JUPYTER_PORT=8899 docker compose up` (also `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT`) |
| Graph looks empty in Neo4j Browser | run `docker compose exec workshop ./setup.sh` |
| Edits to a notebook vanish, or an old version keeps loading | a stale `.ipynb_checkpoints/` copy. `docker compose exec workshop rm -rf notebooks/.ipynb_checkpoints` |
| Files in `data/` owned by `root`, cannot delete (Linux) | the container ran as root. Set `DOCKER_UID=$(id -u)` and `DOCKER_GID=$(id -g)` in `.env`, then `docker compose up --build`. To clear existing root-owned files: `docker run --rm -v "$PWD:/w" alpine rm -rf /w/data/chroma_ffcs` |
| `Permission denied` writing `data/chroma_ffcs` (Windows) | the `user:` line in `docker-compose.yml` is a Linux-only accommodation. Comment it out, then `docker compose up -d --force-recreate workshop` |

### Starting completely over

```bash
docker compose down -v                 # also deletes the graph volume
docker compose up --build -d
docker compose exec workshop ./setup.sh
```

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

That commits about **30 files, 900 KB**. The vector store is rebuilt by `setup.sh`, so it is
deliberately not committed — which is exactly why a fresh clone must run `setup.sh` before the
notebooks will open.

Keep `.gitattributes` in the commit. It forces LF line endings on the shell and Python files, and
without it every student on Windows gets a `setup.sh` that will not run.

**Check before you push:** `.env` must not appear in `git status`. It is gitignored, but a key
pushed once is a key that must be rotated.

The notebooks are committed **with their outputs**, on purpose: students can read the whole
argument before running anything, and the recorded LLM answers are the evidence the notebooks
discuss. If you would rather commit clean notebooks, strip outputs with
`jupyter nbconvert --clear-output --inplace notebooks/*.ipynb` — but then everyone needs an API
key to see the results.
