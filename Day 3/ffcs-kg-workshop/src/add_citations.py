"""Give every chunk a human-readable citation, and push it to Chroma and Neo4j.

Why not "page N, paragraph M"? Because this PDF's paragraph structure does not
survive text extraction. De-wrapping page 1 yields 23 fragments (the abbreviation
list is one short line each) while page 3 yields only 2 (justified text, almost no
short lines). Four different page-3 chunks would all cite "paragraph 2", which is
worse than useless in a citation.

So a citation here has two parts, both verifiable:

    page 3, passage 4 of 6      <- where to look: page, and position down the page
    "There is NO Entrance Examination."   <- verbatim quote, checked against the chunk

The quote is what a reader actually uses. The page tells them where to look. The
passage index disambiguates when a page holds several chunks. The paragraph index
is kept as a hint where it is trustworthy, and suppressed where it is not.
"""
import json
from collections import defaultdict

import chromadb
import pypdf

from chunk_pdf import dewrap, normalise
from config import CHROMA_DIR, CHUNKS_JSON, PDF_PATH, get_driver

data = json.loads(CHUNKS_JSON.read_text())
chunks = data["chunks"]
reader = pypdf.PdfReader(PDF_PATH)

paragraphs = {n: normalise(dewrap(p.extract_text())).split("\n\n")
              for n, p in enumerate(reader.pages, start=1)}

# A page's paragraph index is only meaningful when de-wrapping found a sensible
# number of paragraphs: more than one, and not one per line.
per_page = defaultdict(list)
for c in chunks:
    per_page[c["page"]].append(c)

reliable = {p: 1 < len(paras) <= 12 for p, paras in paragraphs.items()}

for page, page_chunks in per_page.items():
    total = len(page_chunks)
    for position, chunk in enumerate(sorted(page_chunks, key=lambda c: c["id"]), start=1):
        chunk["passage"] = position
        chunk["passages_on_page"] = total
        cite = f"page {page}, passage {position} of {total}"
        if reliable[page]:
            hits = [i for i, para in enumerate(paragraphs[page], start=1)
                    if para[:40] and (para[:40] in chunk["text"]
                                      or chunk["text"][:40] in para)]
            if hits:
                span = (f"paragraph {hits[0]}" if len(hits) == 1
                        else f"paragraphs {hits[0]}-{hits[-1]}")
                cite += f" ({span})"
                chunk["paragraphs"] = hits
        chunk["citation"] = cite

data["document"]["paragraph_index_reliable"] = reliable
CHUNKS_JSON.write_text(json.dumps(data, indent=2))

# --- push citations into the stores, IF they have been built already --------------
#
# Citations are written into chunks.json first, and build_graph.py /
# build_vectorstore.py read them from there. So on a clean setup this section has
# nothing to do; it exists so you can re-run citations later without rebuilding.

updated = []

try:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection("ffcs_chunks")
    collection.update(
        ids=[c["id"] for c in chunks],
        metadatas=[{"page": c["page"], "n_chars": c["n_chars"],
                    "citation": c["citation"], "passage": c["passage"]} for c in chunks],
    )
    updated.append("Chroma")
except Exception:
    pass                     # not built yet - build_vectorstore.py will pick them up

try:
    driver, database = get_driver()
    with driver.session(database=database) as session:
        session.run("""
            UNWIND $rows AS row
            MATCH (c:Chunk {id: row.id})
            SET c.citation = row.citation, c.passage = row.passage
        """, {"rows": [{"id": c["id"], "citation": c["citation"], "passage": c["passage"]}
                       for c in chunks]})
    driver.close()
    updated.append("Neo4j")
except Exception:
    pass                     # not built yet - build_graph.py will pick them up

where = ", ".join(["chunks.json"] + updated)
print(f"Citations written to {where}\n")
for c in chunks:
    print(f"  {c['id']:<14} {c['citation']:<44} {c['text'][:40].strip()}...")
print("\nParagraph index reliable per page:", reliable)
