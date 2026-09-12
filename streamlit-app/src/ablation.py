"""Measure context quality without calling an LLM.

An answer can only be right if the evidence reached the prompt. So before asking
whether the model answered correctly, ask a cheaper and more diagnostic question:

    did the assembled context actually contain what the answer needs?

This is context recall. It needs no API calls, so it runs in class instantly and
costs nothing, and it separates two failures that look identical in the output:
the evidence never arrived, versus the evidence arrived and the model misread it.
"""
import re

from build_vectorstore import embed_query, get_collection, get_model
from config import DEMO
from hybrid_rag import (CENSUS_LABELS, COMPLETE_SET, LABELS_SEEN, NEIGHBOURHOOD,
                        format_fact, labels_from_question)

# (id, question, requirements, kind)
#
# Each requirement is a LIST OF ALTERNATIVES and counts as met if ANY of them appears.
# This matters for fairness: the same fact has two legitimate surface forms. "Fashion
# Technology needs no exam" appears in the text as the sentence "There is NO Entrance
# Examination." and in the graph as the triple "EXEMPT_FROM". Testing only for the
# sentence would score the graph as having lost information it actually holds.
PROBES = [
    ("C1",  "Which entrance exam must a B.Tech Fashion Technology applicant take?",
            [["NO Entrance Examination", "EXEMPT_FROM"]], "local"),
    ("C2",  "Do I need both a UCEED score and a V-DAT score to get into B.Des?",
            [["UCEED score or V-DAT", "condition_group=OR_1"]], "local"),
    ("C13", "How many distinct entrance examinations are named in the document? List them.",
            [["VITEEE"], ["VITMEE"], ["UCEED"], ["V-DAT"]], "global"),
    ("C15", "Which schools are named in the document?",
            [["VIT School of Design"], ["VIT Business School"]], "global"),
    ("C7",  "List all the facilities at the school that offers B.Des.",
            [["PROTICS"], ["3D-iD"], ["Smart PD"], ["Ergonomics Lab"], ["Painting Booth"]],
            "global"),
    ("C9",  "How many Academic Council meetings are referenced in the document?",
            [["18th"], ["20th"], ["27th"], ["28th"], ["37th"], ["46th"], ["59th"],
             ["71st"], ["72nd"], ["Standing Committee"]], "global"),
    ("K1",  "What do employers expect from students?",
            [["multi-disciplinary competency"], ["leadership skills"]], "prose"),
    ("K2",  "What is the main objective of the design programmes at V-SIGN?",
            [["new breed of problem solvers"]], "prose"),
    ("K3",  "How are V-SIGN students trained to approach product design?",
            [["holistic viewpoint"]], "prose"),
]

VARIANTS = ["passages", "graph", "hybrid"]


def assemble(session, question, variant, model, collection, k=4):
    """Build only the blocks a given variant is allowed to use."""
    hit = collection.query(query_embeddings=[embed_query(model, question)],
                           n_results=k, include=["documents", "metadatas"])
    ids, docs, metas = hit["ids"][0], hit["documents"][0], hit["metadatas"][0]

    blocks = []
    if variant in ("passages", "hybrid"):
        blocks.append("PASSAGES:\n" + "\n\n".join(
            f"[{i}] ({m['citation']})\n{d}" for i, d, m in zip(ids, docs, metas)))

    if variant in ("graph", "hybrid"):
        asked = labels_from_question(question)
        facts = [format_fact(r)
                 for r in session.run(NEIGHBOURHOOD, {"ids": ids, "labels": asked})]
        labels = [r["label"] for r in session.run(LABELS_SEEN, {"ids": ids})]
        census = []
        for label in sorted((set(labels) | set(asked)) & CENSUS_LABELS):
            row = session.run(COMPLETE_SET, {"label": label, "demo": DEMO}).single()
            census.append(f"ALL {label} ({row['n']}): " + ", ".join(sorted(row["members"])))
        blocks.append("GRAPH FACTS:\n" + "\n".join(facts))
        blocks.append("COMPLETE SETS:\n" + "\n".join(census))

    return ids, "\n\n".join(blocks)


def recall(context, requirements):
    """A requirement is met if ANY of its alternative surface forms is present."""
    low = context.lower()
    found, missing = [], []
    for alternatives in requirements:
        hit = next((a for a in alternatives if a.lower() in low), None)
        (found if hit else missing).append(hit or alternatives[0])
    return found, missing


def run(session, model=None, collection=None, k=4):
    model = model or get_model()
    collection = collection or get_collection()
    rows = []
    for qid, question, required, kind in PROBES:
        row = {"id": qid, "question": question, "kind": kind, "required": len(required)}
        for variant in VARIANTS:
            _, context = assemble(session, question, variant, model, collection, k)
            found, missing = recall(context, required)
            row[variant] = len(found)
            row[variant + "_missing"] = missing
            row[variant + "_chars"] = len(context)
        rows.append(row)
    return rows
