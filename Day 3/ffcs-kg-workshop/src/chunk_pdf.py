"""Step 2 of the workshop: extract and chunk the source PDF.

Produces data/chunks.json, the provenance layer of the graph.
Each chunk carries a stable id (chunk_p3_02) and its page number, so every
(:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(:Document) path can cite a page.

Chunking is deliberately generic. The de-wrap heuristic uses only line geometry
and punctuation, never this document's wording, and the splitter is stock
RecursiveCharacterTextSplitter. Hand-placing boundaries around the facts we
want to demonstrate would rig the step-6 comparison against naive RAG.
"""

import json
import re
import statistics
import pypdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNKS_JSON, CHUNKS_PREVIEW, PDF_PATH

OUT_JSON = CHUNKS_JSON
OUT_PREVIEW = CHUNKS_PREVIEW

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100

# Surface-form normalisation. Applied to chunk text so entity linking sees canonical
# names, and so a chunk reads with the same spelling the graph uses. The source's own
# typos ("Mechnical", "abbrevations") are corrected here, not silently in the graph.
NORMALISATIONS = [
    (r"\bMechnical\b", "Mechanical"),
    (r"\babbrevations\b", "abbreviations"),
    (r"\bBTech\b", "B.Tech"),
    (r"\bB\.Tech\.(?=[A-Z])", "B.Tech "),   # "B.Tech.Fashion" -> "B.Tech Fashion"
    (r"\bBDes\b", "B.Des"),
    (r"\bMTech\b", "M.Tech"),
    (r"\bMDes\b", "M.Des"),
]


def dewrap(raw: str) -> str:
    """Rejoin hard-wrapped PDF lines into paragraphs.

    A line ends a paragraph when it is clearly short relative to the page's
    typical line width, or when the next line opens a numbered list item.
    Both signals are layout-based and document-agnostic.
    """
    lines = [ln.rstrip() for ln in raw.split("\n") if ln.strip()]
    if not lines:
        return ""

    widths = [len(ln) for ln in lines]
    typical = statistics.median(widths)
    short_line = typical * 0.75

    paragraphs, current = [], []
    for i, line in enumerate(lines):
        current.append(line.strip())
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else None

        ends_para = (
            nxt is None
            or len(line) < short_line                    # short line = paragraph end
            or re.match(r"^\d+\.\s", nxt)                # next line starts a list item
        )
        if ends_para:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    text = "\n\n".join(paragraphs)
    text = re.sub(r"[ \t]{2,}", " ", text)               # PDF justification padding
    return text.strip()


def normalise(text: str) -> str:
    for pattern, replacement in NORMALISATIONS:
        text = re.sub(pattern, replacement, text)
    return re.sub(r"[ \t]{2,}", " ", text)


def main() -> None:
    reader = pypdf.PdfReader(PDF_PATH)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = normalise(dewrap(page.extract_text()))
        for position, piece in enumerate(splitter.split_text(page_text), start=1):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append({
                "id": f"chunk_p{page_number}_{position:02d}",
                "page": page_number,
                "position_on_page": position,
                "text": piece,
                "n_chars": len(piece),
                "n_words": len(piece.split()),
            })

    document = {
        "id": "small.pdf",
        "title": "VIT FFCS Academic Regulations 4.0 (extract)",
        "pages": len(reader.pages),
        "truncated": True,
        "truncation_note": (
            "Page 3 ends mid-sentence at '...Score is considered for admissions to the "
            "BDes'. The M.Des admission route is absent from the source."
        ),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "n_chunks": len(chunks),
    }

    OUT_JSON.write_text(json.dumps({"document": document, "chunks": chunks}, indent=2))

    lines = [
        f"# Chunk preview — {document['title']}",
        "",
        f"{len(chunks)} chunks from {document['pages']} pages "
        f"(size {CHUNK_SIZE}, overlap {CHUNK_OVERLAP}).",
        "",
    ]
    for chunk in chunks:
        lines += [
            f"## `{chunk['id']}` — page {chunk['page']}, {chunk['n_chars']} chars",
            "",
            chunk["text"],
            "",
        ]
    OUT_PREVIEW.write_text("\n".join(lines))

    print(f"{len(chunks)} chunks written to {OUT_JSON} and {OUT_PREVIEW}")
    for chunk in chunks:
        head = chunk["text"][:72].replace("\n", " ")
        print(f"  {chunk['id']}  p{chunk['page']}  {chunk['n_chars']:>4}c  {head}...")


if __name__ == "__main__":
    main()
