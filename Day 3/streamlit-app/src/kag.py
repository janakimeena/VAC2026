"""KAG retrieval: answer questions by querying the graph, not the text.

Each entry pairs a question with the Cypher that answers it. In a production KAG
system an LLM generates this Cypher from the schema; here it is written out so the
mechanism is visible and the demo is deterministic. The point being illustrated is
not "an LLM can write Cypher" but "the answer is a traversal, not a text lookup".

Every answer also collects its provenance by following MENTIONED_IN back to the
chunks, so KAG cites sources exactly like RAG does.
"""

from config import DEMO, get_driver

QUERIES = {

"C4": ("On what date was FFCS Academic Regulations 4.0 approved?", """
    MATCH (r:Regulation {version: '4.0'})-[:APPROVED_IN]->(m:CouncilMeeting)
    RETURN m.name AS meeting, m.date AS printed_date, m.date_known AS date_known
"""),

"C5": ("Which entrance exam ranks are used to admit students to M.Tech?", """
    MATCH (p:Programme {name: 'M.Tech'})-[e:ADMITS_VIA]->(x:EntranceExam)
    RETURN x.name AS exam, x.full_name AS full_name, e.source_note AS source_note
"""),

"C6": ("How many FFCS regulation versions came before version 4.0? List them in order.", """
    MATCH path = (:Regulation {version: '4.0'})-[:SUPERSEDES*]->(r:Regulation)
    RETURN count(DISTINCT r) AS versions_before,
           [x IN collect(DISTINCT r.version) | x] AS versions
"""),

"C7": ("List all the facilities at the school that offers B.Des.", """
    MATCH (p:Programme {name: 'B.Des'})<-[:OFFERS]-(s:School)-[:HAS_FACILITY]->(f:Facility)
    RETURN s.name AS school, count(f) AS n, collect(f.name) AS facilities
"""),

"C8": ("Which programmes require no entrance examination at all?", """
    MATCH (p:Programme)
    OPTIONAL MATCH (p)-[:ADMITS_VIA]->(x:EntranceExam)
    WITH p, count(x) AS exams
    WHERE exams = 0
    RETURN p.name AS programme,
           p.admission_information_status AS status,
           CASE p.admission_information_status
             WHEN 'NOT_STATED_IN_SOURCE'
               THEN 'UNKNOWN - the document does not state the admission route'
             ELSE 'CONFIRMED - the document explicitly states no entrance exam'
           END AS interpretation
    ORDER BY status, programme
"""),

"C9": ("How many Academic Council meetings are referenced in the document?", """
    MATCH (m:CouncilMeeting {demo: $demo})
    RETURN count(m) AS n, collect(m.name) AS meetings
"""),

"C12": ("Which course basket has no abbreviation defined in the document?", """
    MATCH (b:CourseBasket {demo: $demo})
    WHERE NOT (:Abbreviation)-[:ABBREVIATES]->(b)
    RETURN collect(b.name) AS baskets_without_abbreviation
"""),

"C13": ("How many distinct entrance examinations are named? List them.", """
    MATCH (x:EntranceExam {demo: $demo})
    RETURN count(x) AS n, collect(x.name + ' (' + x.full_name + ')') AS exams
"""),

"C14": ("List all the features of FFCS described in the document.", """
    MATCH (:System {name: 'FFCS'})-[:HAS_FEATURE]->(f:Feature)
    WITH f ORDER BY f.number
    RETURN count(f) AS n,
           collect(toString(f.number) + '. ' + left(f.text, 60) + '...') AS features
    ORDER BY n
"""),

"C15": ("Which schools are named in the document?", """
    MATCH (s:School {demo: $demo})
    RETURN count(s) AS n, collect(s.name + coalesce(' (' + s.alias + ')', '')) AS schools
"""),

"C16": ("How many course baskets are students allowed to choose from?", """
    MATCH (b:CourseBasket {demo: $demo})
    RETURN count(b) AS n, collect(b.name) AS baskets
"""),

"C17": ("Is a V-DAT score accepted for admission to M.Des?", """
    MATCH (p:Programme {name: 'M.Des'})
    OPTIONAL MATCH (p)-[:REQUIRES]->(c:AdmissionCriterion {name: 'V-DAT score'})
    OPTIONAL MATCH (p)-[:ADMITS_VIA]->(x:EntranceExam {name: 'V-DAT'})
    RETURN p.admission_information_status AS status, p.status_reason AS reason,
           count(c) + count(x) AS supporting_edges
"""),

"C1": ("Which entrance exam must a B.Tech Fashion Technology applicant take?", """
    MATCH (p:Programme {name: 'B.Tech Fashion Technology'})
    OPTIONAL MATCH (p)-[:ADMITS_VIA]->(x:EntranceExam)
    OPTIONAL MATCH (p)-[e:EXEMPT_FROM]->(ex:EntranceExam)
    RETURN count(x) AS required_exams, ex.name AS exempt_from, e.evidence AS evidence
"""),

"C2": ("Do I need both a UCEED score and a V-DAT score for B.Des?", """
    MATCH (p:Programme {name: 'B.Des'})-[e:REQUIRES]->(c:AdmissionCriterion)
    RETURN e.condition_group AS group, collect(c.name) AS criteria,
           CASE WHEN e.condition_group STARTS WITH 'OR'
                THEN 'ANY ONE of these' ELSE 'ALL of these' END AS reading
    ORDER BY group
"""),

"C3": ("How is a student admitted to M.Des?", """
    MATCH (p:Programme {name: 'M.Des'})
    OPTIONAL MATCH (p)-[:ADMITS_VIA]->(x:EntranceExam)
    OPTIONAL MATCH (p)-[:REQUIRES]->(c:AdmissionCriterion)
    RETURN p.admission_information_status AS status, p.status_reason AS reason,
           collect(DISTINCT x.name) AS exams, collect(DISTINCT c.name) AS criteria
"""),
}

# Entities whose provenance is worth showing per question.
PROVENANCE = {
    "C1": ("Programme", "B.Tech Fashion Technology"),
    "C2": ("Programme", "B.Des"),
    "C3": ("Programme", "M.Des"),
    "C7": ("School", "VIT School of Design"),
    "C5": ("Programme", "M.Tech"),
}


def connect():
    """Open a Neo4j connection using the settings in config.py / the environment."""
    return get_driver()


def run(session, key):
    question, cypher = QUERIES[key]
    rows = [dict(r) for r in session.run(cypher, {"demo": DEMO})]
    return question, cypher.strip(), rows


def provenance(session, key):
    if key not in PROVENANCE:
        return []
    label, name = PROVENANCE[key]
    return [dict(r) for r in session.run(f"""
        MATCH (n:{label} {{name: $name}})-[:MENTIONED_IN]->(c:Chunk)-[:PART_OF]->(d:Document)
        RETURN c.id AS chunk, c.page AS page, d.id AS document
        ORDER BY c.id
    """, {"name": name})]


if __name__ == "__main__":
    driver, db = connect()
    with driver.session(database=db) as session:
        for key in QUERIES:
            question, cypher, rows = run(session, key)
            print("=" * 100)
            print(f"[{key}] {question}")
            for row in rows:
                for k, v in row.items():
                    print(f"    {k:<28} {v}")
            src = provenance(session, key)
            if src:
                print(f"    {'provenance':<28} {[s['chunk'] for s in src]}")
    driver.close()
