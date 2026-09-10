"""Can the graph answer this at all? A fair test of KG coverage.

Rather than hand-writing a Cypher query per question and declaring failure when it
returns nothing, this searches EVERY property of EVERY node and relationship in the
graph for the terms the answer needs. If the content is not there in any form, no
Cypher query could have found it - the ontology simply did not model it.
"""
from config import DEMO, get_driver

SEARCH = """
MATCH (n {demo: $demo})
WHERE NOT n:Chunk AND NOT n:Document
UNWIND keys(n) AS key
WITH n, key WHERE key <> 'embedding'
WITH n, key, apoc.convert.toJson(n[key]) AS value
WHERE any(t IN $terms WHERE toLower(value) CONTAINS toLower(t))
RETURN 'node' AS kind, labels(n)[0] AS label,
       coalesce(n.name, n.version, toString(n.number)) AS entity,
       key, left(value, 120) AS value
UNION
MATCH ()-[r {demo: $demo}]->()
UNWIND keys(r) AS key
WITH r, key, apoc.convert.toJson(r[key]) AS value
WHERE any(t IN $terms WHERE toLower(value) CONTAINS toLower(t))
RETURN 'rel' AS kind, type(r) AS label, '' AS entity, key, left(value, 120) AS value
"""

# Same search, but over the chunk text, to prove the fact IS in the document.
IN_TEXT = """
MATCH (c:Chunk {demo: $demo})
WHERE any(t IN $terms WHERE toLower(c.text) CONTAINS toLower(t))
RETURN c.id AS chunk, c.citation AS citation
ORDER BY chunk
"""


def coverage(session, terms):
    graph = [dict(r) for r in session.run(SEARCH, {"demo": DEMO, "terms": terms})]
    text = [dict(r) for r in session.run(IN_TEXT, {"demo": DEMO, "terms": terms})]
    return graph, text


CASES = [
    ("K1", "What do employers expect from students?",
     ["multi-disciplinary competency", "leadership skills"]),
    ("K2", "What is the main objective of the design programmes at V-SIGN?",
     ["new breed of problem solvers"]),
    ("K3", "How are V-SIGN students trained to approach product design?",
     ["holistic viewpoint", "balanced and harmonious"]),
    ("K4", "What kind of building houses the design facilities?",
     ["sprawling", "new building"]),
    ("K5", "Why does VIT say present-day students need a flexible system?",
     ["make decisions on their own", "plan their future"]),
    ("K6", "Does being called for counselling guarantee admission to Fashion Technology?",
     ["does not guarantee admission"]),
    ("K7", "Whose interpretation is final and binding in a dispute over the rules?",
     ["final and binding"]),
    ("K8", "What is VTOP used for?",
     ["academic software", "submissions related to project"]),
    ("K9", "What helps slow learners under FFCS?",
     ["slow learners"]),
    ("K10", "What does the document say about research for UG students?",
     ["research activities"]),
]

if __name__ == "__main__":
    driver, database = get_driver()
    with driver.session(database=database) as session:
        print(f"{'id':<5} {'question':<62} {'in graph?':<11} {'in text?'}")
        print("-" * 104)
        for cid, question, terms in CASES:
            graph, text = coverage(session, terms)
            print(f"{cid:<5} {question[:60]:<62} "
                  f"{('YES ' + str(len(graph))) if graph else 'NO':<11} "
                  f"{('YES ' + str([t['chunk'] for t in text])) if text else 'NO'}")
        print()
        for cid, question, terms in CASES:
            graph, text = coverage(session, terms)
            if graph:
                print(f"[{cid}] found in graph:")
                for g in graph[:3]:
                    print(f"    {g['kind']} {g['label']} {g['entity']} .{g['key']} = {g['value'][:90]}")
    driver.close()
