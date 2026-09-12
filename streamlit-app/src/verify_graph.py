"""Verification: run the workshop's questions against the graph as Cypher.

Each query is the one a KAG pipeline would generate. Printing them here proves the
graph answers correctly before any LLM is involved, so a wrong answer in step 6 can
be attributed to the pipeline rather than the data.
"""
from config import DEMO, get_driver

QUERIES = [
("CASE 1 — explicit negative: which B.Tech needs no entrance exam?", """
    MATCH (p:Programme)-[e:EXEMPT_FROM]->(x:EntranceExam)
    RETURN p.name AS programme, x.name AS exempt_from, e.evidence AS evidence
"""),
("CASE 2 — logical structure: what does a B.Des applicant need?", """
    MATCH (p:Programme {name: 'B.Des'})-[e:REQUIRES]->(c:AdmissionCriterion)
    RETURN e.condition_group AS group,
           collect(c.name) AS criteria,
           CASE WHEN e.condition_group STARTS WITH 'OR' THEN 'any one of these'
                ELSE 'all of these' END AS reading
    ORDER BY group
"""),
("CASE 3 — not stated: how is a student admitted to M.Des?", """
    MATCH (p:Programme {name: 'M.Des'})
    OPTIONAL MATCH (p)-[:ADMITS_VIA]->(x:EntranceExam)
    OPTIONAL MATCH (p)-[:REQUIRES]->(c:AdmissionCriterion)
    RETURN p.admission_information_status AS status, p.status_reason AS reason,
           collect(DISTINCT x.name) AS exams, collect(DISTINCT c.name) AS criteria
"""),
("Control (single chunk) — which meeting approved the CAL regulation?", """
    MATCH (c:Concept {name: 'CAL'})<-[:FOCUSES_ON]-(r:Regulation)-[:APPROVED_IN]->(m:CouncilMeeting)
    RETURN r.name AS regulation, m.name AS meeting, m.date AS date
"""),
("Multi-hop (split chunks) — facilities of the school offering B.Des", """
    MATCH (p:Programme {name: 'B.Des'})<-[:OFFERS]-(s:School)-[:HAS_FACILITY]->(f:Facility)
    RETURN s.name AS school, collect(f.name) AS facilities
"""),
("Multi-hop (split chunks) — what does v4.0 replace, approved when?", """
    MATCH (a:Regulation {version: '4.0'})-[:SUPERSEDES]->(b:Regulation)-[:APPROVED_IN]->(m:CouncilMeeting)
    RETURN a.version AS current, b.name AS replaces, m.name AS approved_in, m.date AS date
"""),
("Editorial correction — which exam does an M.Tech applicant sit?", """
    MATCH (p:Programme {name: 'M.Tech'})-[e:ADMITS_VIA]->(x:EntranceExam)
    RETURN x.name AS exam, x.full_name AS full_name, e.source_note AS source_note
"""),
("Unknown value — regulations approved at a meeting with no known date", """
    MATCH (r:Regulation)-[:APPROVED_IN]->(m:CouncilMeeting)
    WHERE m.date_known = false
    RETURN r.name AS regulation, m.name AS meeting, m.date AS printed_date, m.date_known AS date_known
"""),
("Aggregation — course baskets and their abbreviations", """
    MATCH (a:Abbreviation)-[:ABBREVIATES]->(b:CourseBasket)
    RETURN collect(a.short + ' = ' + b.name) AS baskets
"""),
("Cohort — who does FFCS 4.0 apply to?", """
    MATCH (r:Regulation {version: '4.0'})-[:APPLIES_TO]->(c:Cohort)
    RETURN c.name AS cohort, c.academic_year AS academic_year
"""),
("PROVENANCE — where does the Fashion Technology fact come from?", """
    MATCH (p:Programme {name: 'B.Tech Fashion Technology'})-[:MENTIONED_IN]->(c:Chunk)-[:PART_OF]->(d:Document)
    RETURN c.id AS chunk, c.page AS page, d.id AS document,
           left(c.text, 90) + '...' AS excerpt
"""),
]


def main():
    driver, database = get_driver()
    with driver.session(database=database) as session:
        for title, cypher in QUERIES:
            print("\n" + "=" * 92)
            print(title)
            print("-" * 92)
            records = list(session.run(cypher))
            if not records:
                print("  (no rows — the graph asserts nothing here)")
            for rec in records:
                for key, value in rec.items():
                    print(f"  {key:<16} {value}")
                print()
    driver.close()


if __name__ == "__main__":
    main()
