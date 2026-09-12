"""Step 3: build the FFCS knowledge graph in Neo4j.

    python src/build_graph.py

Connection settings come from the environment (see config.py and .env.example),
so the same command works against the workshop's local Neo4j or a cloud instance.

Every node and relationship carries demo:'ffcs_kg', so the wipe at the start
removes only this demo's data and leaves anything else in the database alone.

Data: graph_data.py. Provenance chunks: data/chunks.json.

To see the schema once it is loaded, run this in the Neo4j Browser:
    CALL db.schema.visualization()
"""

import json
import re
import sys
import graph_data as D
from config import CHUNKS_JSON, get_driver, neo4j_settings

DEMO = D.DEMO


class GraphBuilder:
    def __init__(self, driver, database):
        self.driver = driver
        self.database = database
        self.counts = {}

    def run(self, cypher, params=None):
        with self.driver.session(database=self.database) as session:
            return list(session.run(cypher, params or {}))

    def step(self, label, cypher, params=None):
        result = self.run(cypher, params)
        if result and "n" in result[0].keys():
            n = result[0]["n"]
        else:
            n = len(params.get("rows", [])) if params and "rows" in params else len(result)
        self.counts[label] = n
        print(f"  {label:<34} {n:>4}")
        return result

    # -- 1. schema ---------------------------------------------------------------------
    def constraints(self):
        print("\n[1] Constraints and indexes")
        uniques = [
            ("programme_name",  "Programme",         "name"),
            ("exam_name",       "EntranceExam",      "name"),
            ("criterion_name",  "AdmissionCriterion","name"),
            ("regulation_ver",  "Regulation",        "version"),
            ("meeting_name",    "CouncilMeeting",    "name"),
            ("body_name",       "GoverningBody",     "name"),
            ("role_name",       "Role",              "name"),
            ("school_name",     "School",            "name"),
            ("facility_name",   "Facility",          "name"),
            ("basket_name",     "CourseBasket",      "name"),
            ("campus_name",     "Campus",            "name"),
            ("cohort_name",     "Cohort",            "name"),
            ("university_name", "University",        "name"),
            ("chunk_id",        "Chunk",             "id"),
            ("document_id",     "Document",          "id"),
            ("abbrev_short",    "Abbreviation",      "short"),
        ]
        for cname, label, prop in uniques:
            self.run(f"CREATE CONSTRAINT {cname} IF NOT EXISTS "
                     f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
        # Feature is keyed by number, System/Concept share a name space.
        self.run("CREATE CONSTRAINT feature_number IF NOT EXISTS "
                 "FOR (n:Feature) REQUIRE n.number IS UNIQUE")
        self.run("CREATE INDEX system_name IF NOT EXISTS FOR (n:System) ON (n.name)")
        self.run("CREATE INDEX concept_name IF NOT EXISTS FOR (n:Concept) ON (n.name)")
        print(f"  {'constraints + indexes':<34} {len(uniques) + 3:>4}")

    def wipe(self):
        print("\n[0] Removing previous run of this demo")
        removed = self.run(
            "MATCH (n {demo: $demo}) WITH n, count(*) AS _ DETACH DELETE n "
            "RETURN count(_) AS removed", {"demo": DEMO})
        print(f"  {'nodes removed':<34} {removed[0]['removed'] if removed else 0:>4}")

    # -- 2. provenance layer -----------------------------------------------------------
    def provenance(self):
        print("\n[2] Provenance layer (Document, Chunk)")
        data = json.loads(CHUNKS_JSON.read_text())
        # Neo4j stores only primitives and arrays of primitives, so nested values
        # (chunks.json carries a per-page map of flags) are dropped rather than
        # crashing the load.
        doc = {k: v for k, v in data["document"].items()
               if isinstance(v, (str, int, float, bool))
               or (isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v))}
        self.step("Document", """
            MERGE (d:Document {id: $doc.id})
            SET d += $doc, d.demo = $demo
        """, {"doc": doc, "demo": DEMO})
        self.counts["Document"] = 1
        self.step("Chunk", """
            UNWIND $rows AS row
            MERGE (c:Chunk {id: row.id})
            SET c.page = row.page, c.text = row.text,
                c.n_chars = row.n_chars, c.n_words = row.n_words,
                c.citation = row.citation, c.passage = row.passage, c.demo = $demo
            WITH c
            MATCH (d:Document {id: $doc_id})
            MERGE (c)-[r:PART_OF]->(d) SET r.demo = $demo
            RETURN count(c) AS n
        """, {"rows": data["chunks"], "doc_id": data["document"]["id"], "demo": DEMO})
        return data["chunks"]

    # -- 3. core entities --------------------------------------------------------------
    def entities(self):
        print("\n[3] Core domain entities")
        self.step("University", """
            MERGE (u:University {name: $row.name}) SET u += $row, u.demo = $demo
        """, {"row": D.UNIVERSITY, "demo": DEMO})
        self.counts["University"] = 1

        self.step("Campus", """
            UNWIND $rows AS row
            MERGE (c:Campus {name: row.name}) SET c += row, c.demo = $demo
            WITH c MATCH (u:University {name: $uni})
            MERGE (u)-[r:HAS_CAMPUS]->(c) SET r.demo = $demo
        """, {"rows": D.CAMPUSES, "uni": D.UNIVERSITY["name"], "demo": DEMO})

        for label, rows, key in [
            ("Cohort",             D.COHORTS,            "name"),
            ("GoverningBody",      D.GOVERNING_BODIES,   "name"),
            ("Role",               D.ROLES,              "name"),
            ("Regulation",         D.REGULATIONS,        "version"),
            ("CouncilMeeting",     D.COUNCIL_MEETINGS,   "name"),
            ("CourseBasket",       D.COURSE_BASKETS,     "name"),
            ("Facility",           D.FACILITIES,         "name"),
            ("EntranceExam",       D.ENTRANCE_EXAMS,     "name"),
            ("AdmissionCriterion", D.ADMISSION_CRITERIA, "name"),
            ("Programme",          D.PROGRAMMES,         "name"),
            ("School",             D.SCHOOLS,            "name"),
        ]:
            self.step(label, f"""
                UNWIND $rows AS row
                MERGE (n:{label} {{{key}: row.{key}}})
                SET n += row, n.demo = $demo
            """, {"rows": rows, "demo": DEMO})

        self.step("System", """
            UNWIND $rows AS row
            MERGE (n:System {name: row.name}) SET n += row, n.demo = $demo
        """, {"rows": D.SYSTEMS, "demo": DEMO})

        self.step("Concept", """
            UNWIND $rows AS row
            MERGE (n:Concept {name: row.name}) SET n += row, n.demo = $demo
        """, {"rows": D.CONCEPTS, "demo": DEMO})

        self.step("Feature", """
            UNWIND $rows AS row
            MERGE (f:Feature {number: row[0]})
            SET f.text = row[1], f.demo = $demo
            WITH f MATCH (s:System {name: 'FFCS'})
            MERGE (s)-[r:HAS_FEATURE]->(f) SET r.demo = $demo
        """, {"rows": D.FEATURES, "demo": DEMO})

        self.step("Abbreviation", """
            UNWIND $rows AS row
            MERGE (a:Abbreviation {short: row[0]})
            SET a.expansion = row[1], a.demo = $demo
        """, {"rows": D.ABBREVIATIONS, "demo": DEMO})

    # -- 4. relationships --------------------------------------------------------------
    def relationships(self):
        print("\n[4] Relationships")

        self.step("APPROVED_IN", """
            UNWIND $rows AS row
            MATCH (r:Regulation {version: row[0]}), (m:CouncilMeeting {name: row[1]})
            MERGE (r)-[e:APPROVED_IN]->(m) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.APPROVED_IN, "demo": DEMO})

        self.step("SUPERSEDES", """
            UNWIND $rows AS row
            MATCH (a:Regulation {version: row[0]}), (b:Regulation {version: row[1]})
            MERGE (a)-[e:SUPERSEDES]->(b) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.SUPERSEDES, "demo": DEMO})

        self.step("CONVENED_BY", """
            UNWIND $rows AS row
            MATCH (m:CouncilMeeting {name: row[0]}), (g:GoverningBody {name: row[1]})
            MERGE (m)-[e:CONVENED_BY]->(g) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.CONVENED_BY, "demo": DEMO})

        self.step("GOVERNED_BY", """
            UNWIND $rows AS row
            MATCH (r:Regulation {version: '4.0'}), (g:GoverningBody {name: row})
            MERGE (r)-[e:GOVERNED_BY]->(g) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": ["Academic Council", "Academic Policy Committee"], "demo": DEMO})

        self.step("HEADED_BY", """
            MATCH (g:GoverningBody {name: 'Academic Policy Committee'}),
                  (r:Role {name: 'Vice-Chancellor'})
            MERGE (g)-[e:HEADED_BY]->(r) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"demo": DEMO})

        self.step("APPLIES_TO", """
            MATCH (r:Regulation {version: '4.0'}),
                  (c:Cohort {name: 'Students admitted 2021-22 onward'})
            MERGE (r)-[e:APPLIES_TO]->(c) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"demo": DEMO})

        self.step("FOCUSES_ON", """
            MATCH (r:Regulation {version: '3.0'}), (c:Concept {name: 'CAL'})
            MERGE (r)-[e:FOCUSES_ON]->(c) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"demo": DEMO})

        self.step("INTRODUCED_BY", """
            MATCH (s:System {name: 'FFCS'}), (u:University {name: $uni})
            MERGE (s)-[e:INTRODUCED_BY]->(u) SET e.year = 2008, e.demo = $demo
            RETURN count(e) AS n
        """, {"uni": D.UNIVERSITY["name"], "demo": DEMO})

        self.step("REFERS_TO", """
            UNWIND $rows AS row
            MATCH (f:Feature {number: row[0]}), (b:CourseBasket {name: row[1]})
            MERGE (f)-[e:REFERS_TO]->(b) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.FEATURE_REFERS_TO, "demo": DEMO})

        self.step("ABBREVIATES", """
            UNWIND $rows AS row
            MATCH (a:Abbreviation {short: row[0]})
            CALL (row) {
                MATCH (t) WHERE row[3] IN [t.name] AND row[2] IN labels(t) AND t.demo = $demo
                RETURN t LIMIT 1
            }
            MERGE (a)-[e:ABBREVIATES]->(t) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.ABBREVIATIONS, "demo": DEMO})

        self.step("OFFERS", """
            UNWIND $rows AS row
            MATCH (s:School {name: row[0]}), (p:Programme {name: row[1]})
            MERGE (s)-[e:OFFERS]->(p) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.OFFERS, "demo": DEMO})

        self.step("HAS_FACILITY", """
            UNWIND $rows AS row
            MATCH (s:School {name: row[0]}), (f:Facility {name: row[1]})
            MERGE (s)-[e:HAS_FACILITY]->(f) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.HAS_FACILITY, "demo": DEMO})

        self.step("LOCATED_AT", """
            MATCH (s:School {name: 'VIT School of Design'}), (c:Campus {name: 'VIT Vellore'})
            MERGE (s)-[e:LOCATED_AT]->(c) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"demo": DEMO})

        self.step("CONDUCTED_BY", """
            UNWIND $rows AS row
            MATCH (x:EntranceExam {name: row[0]}), (u:University {name: row[1]})
            MERGE (x)-[e:CONDUCTED_BY]->(u) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.CONDUCTED_BY, "demo": DEMO})

        self.step("ADVISES", """
            UNWIND $rows AS row
            MATCH (a:Role {name: row[0]}), (b:Role {name: row[1]})
            MERGE (a)-[e:ADVISES]->(b) SET e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": D.ADVISES, "demo": DEMO})

        # --- the three epistemic cases ------------------------------------------------
        self.step("ADMITS_VIA", """
            UNWIND $rows AS row
            MATCH (p:Programme {name: row[0]}), (x:EntranceExam {name: row[1]})
            MERGE (p)-[e:ADMITS_VIA]->(x) SET e += row[2], e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": [list(r) for r in D.ADMITS_VIA], "demo": DEMO})

        self.step("EXEMPT_FROM", """
            UNWIND $rows AS row
            MATCH (p:Programme {name: row[0]}), (x:EntranceExam {name: row[1]})
            MERGE (p)-[e:EXEMPT_FROM]->(x) SET e += row[2], e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": [list(r) for r in D.EXEMPT_FROM], "demo": DEMO})

        self.step("REQUIRES", """
            UNWIND $rows AS row
            MATCH (p:Programme {name: row[0]}), (c:AdmissionCriterion {name: row[1]})
            MERGE (p)-[e:REQUIRES]->(c) SET e += row[2], e.demo = $demo
            RETURN count(e) AS n
        """, {"rows": [list(r) for r in D.REQUIRES], "demo": DEMO})

    # -- 5. entity linking -------------------------------------------------------------
    def mentioned_in(self, chunks):
        """Link core entities to the chunks whose text mentions them.

        Deterministic surface-form matching, not an LLM. Each entity carries the
        aliases the document actually uses, so 'BTech CSE' and 'B.Tech CSE' resolve
        to one node instead of creating two.
        """
        print("\n[5] Provenance links (MENTIONED_IN)")

        targets = []   # (label, key_prop, key_value, [surface forms])

        def add(label, key, value, forms):
            forms = [f for f in forms if f and len(f) >= 3]
            if forms:
                targets.append((label, key, value, forms))

        for p in D.PROGRAMMES:
            forms = [p["name"]] + p.get("aliases", [])
            # "B.Tech CSE, EEE, ECE, Civil, Mechanical" — only the first is written out
            # in full, so the branch token alone has to resolve to its programme node.
            tail = p["name"].replace("B.Tech ", "").replace("M.Tech", "")
            if p["name"].startswith("B.Tech ") and tail not in ("Fashion Technology",):
                forms.append(tail)
            add("Programme", "name", p["name"], forms)
        for x in D.ENTRANCE_EXAMS:
            add("EntranceExam", "name", x["name"], [x["name"], x.get("full_name")])
        for s in D.SCHOOLS:
            add("School", "name", s["name"], [s["name"], s.get("alias")])
        for f in D.FACILITIES:
            add("Facility", "name", f["name"], [f["name"]])
        for b in D.COURSE_BASKETS:
            add("CourseBasket", "name", b["name"], [b["name"]])
        for m in D.COUNCIL_MEETINGS:
            forms = [m["name"]]
            if m["number"]:                      # source also writes "71st meeting of the ..."
                forms.append(f"{m['name'].split()[0]} meeting of the Academic Council")
                forms.append(f"{m['name'].split()[0]} Academic Council")
            add("CouncilMeeting", "name", m["name"], forms)
        for g in D.GOVERNING_BODIES:
            forms = [g["name"]]
            if g["name"].startswith("Standing Committee"):
                forms.append("Standing Committee meeting of the Academic Council")
                forms.append("Standing Committee")
            add("GoverningBody", "name", g["name"], forms)
        for r in D.ROLES:
            add("Role", "name", r["name"], [r["name"], r["name"].split(" / ")[0]])
        for s in D.SYSTEMS:
            add("System", "name", s["name"], [s["name"], s.get("full_name")])
        for c in D.CONCEPTS:
            add("Concept", "name", c["name"], [c["name"], c.get("full_name")])
        # Criterion names are analytic labels; several never appear verbatim, so each
        # carries the surface form the document actually uses as evidence.
        criterion_forms = {
            "VITEEE rank": ["VITEEE rank", "VITEEE ranks"],
            "VITMEE rank": ["VITMEE rank", "VITMEE ranks", "based on their VITEEE ranks"],
            "UCEED score": ["UCEED score", "UCEED"],
            "V-DAT score": ["V-DAT score", "V-DAT"],
            "10+2 marks": ["10+2 marks"],
            "subject of study": ["subject of study"],
            "merit list": ["Merit list", "merit list"],
            "counselling": ["counselling", "counseling"],
            "seat availability": ["availability of seats", "number of seats"],
            "work experience": ["Work experience", "work experience"],
        }
        for c in D.ADMISSION_CRITERIA:
            add("AdmissionCriterion", "name", c["name"],
                criterion_forms.get(c["name"], [c["name"]]))
        for u in [D.UNIVERSITY]:
            add("University", "name", u["name"], [u["name"]])
        for c in D.CAMPUSES:
            add("Campus", "name", c["name"], [c["name"], "VIT, Vellore", "Vellore"])
        for c in D.COHORTS:
            add("Cohort", "name", c["name"], ["2021 - 22", "2021-22"])
        for r in D.REGULATIONS:
            forms = [r["name"]]
            if r["version"] == "separate":
                forms.append("separate Regulations")
            else:
                forms += [f"Regulations Version {r['version']}",
                          f"Regulations {r['version']}"]
            add("Regulation", "version", r["version"], forms)

        # Features have no name; match a distinctive opening slice of their text instead.
        feature_probes = [(number, re.sub(r"\s+", " ", text)[:45].lower())
                          for number, text in D.FEATURES]

        rows = []
        for label, key, value, forms in targets:
            for chunk in chunks:
                text = chunk["text"]
                # trailing "s" tolerated so "Employer" matches "Employers"
                hit = next((f for f in forms
                            if re.search(r"(?<!\w)" + re.escape(f) + r"s?(?!\w)", text, re.I)),
                           None)
                if hit:
                    rows.append({"label": label, "key": key, "value": value,
                                 "chunk": chunk["id"], "surface_form": hit})

        for number, probe in feature_probes:
            for chunk in chunks:
                flat = re.sub(r"\s+", " ", chunk["text"]).lower()
                if probe in flat:
                    rows.append({"label": "Feature", "key": "number", "value": number,
                                 "chunk": chunk["id"], "surface_form": probe[:30] + "..."})

        for label in sorted({r["label"] for r in rows}):
            subset = [r for r in rows if r["label"] == label]
            self.run(f"""
                UNWIND $rows AS row
                MATCH (n:{label}) WHERE n[row.key] = row.value AND n.demo = $demo
                MATCH (c:Chunk {{id: row.chunk}})
                MERGE (n)-[e:MENTIONED_IN]->(c)
                SET e.surface_form = row.surface_form, e.demo = $demo
            """, {"rows": subset, "demo": DEMO})
        self.counts["MENTIONED_IN"] = len(rows)
        print(f"  {'MENTIONED_IN':<34} {len(rows):>4}")

        orphans = self.run("""
            MATCH (n {demo: $demo})
            WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Abbreviation
              AND NOT (n)-[:MENTIONED_IN]->(:Chunk)
            RETURN labels(n)[0] AS label,
                   coalesce(n.name, n.version, 'feature ' + toString(n.number)) AS name
            ORDER BY label, name
        """, {"demo": DEMO})
        if orphans:
            print(f"  entities with no chunk link:  {len(orphans)}")
            for o in orphans:
                print(f"      - {o['label']}: {o['name']}")

    def summary(self):
        print("\n[6] Graph summary")
        for row in self.run("""
            MATCH (n {demo: $demo}) RETURN labels(n)[0] AS label, count(*) AS n
            ORDER BY n DESC, label
        """, {"demo": DEMO}):
            print(f"  {row['label']:<34} {row['n']:>4}")
        totals = self.run("""
            MATCH (n {demo: $demo}) WITH count(n) AS nodes
            MATCH ()-[r {demo: $demo}]->() RETURN nodes, count(r) AS rels
        """, {"demo": DEMO})[0]
        print(f"\n  TOTAL nodes {totals['nodes']}, relationships {totals['rels']}")


def main():
    print(f"Connecting to {neo4j_settings()['uri']}")
    driver, database = get_driver()
    builder = GraphBuilder(driver, database)
    builder.wipe()
    builder.constraints()
    chunks = builder.provenance()
    builder.entities()
    builder.relationships()
    builder.mentioned_in(chunks)
    builder.summary()
    driver.close()
    print("\nDone. Neo4j Browser: http://localhost:7474")


if __name__ == "__main__":
    main()
