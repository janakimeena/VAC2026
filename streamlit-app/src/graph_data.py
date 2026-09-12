"""The contents of the graph, transcribed by hand from data/small.pdf.

Every item here is traceable to a sentence in the source. Where the document is
silent the data records the silence (see M.Des) rather than guessing.

This file is the *what*; build_graph.py is the *how*. Read this one to see what the
graph claims, without reading any Cypher.
"""

DEMO = "ffcs_kg"          # marker on every node/edge, so cleanup touches only this demo

UNIVERSITY = {"name": "VIT University"}
CAMPUSES = [{"name": "VIT Vellore", "location": "Vellore"}]

COHORTS = [{
    "name": "Students admitted 2021-22 onward",
    "academic_year": "2021-22",
    "description": "Students admitted in the academic year 2021-22 and to be admitted in "
                   "the future into various programmes.",
}]

GOVERNING_BODIES = [
    {"name": "Academic Council"},
    {"name": "Academic Policy Committee"},
    {"name": "Standing Committee of the Academic Council"},
    {"name": "Management"},
]

ROLES = [
    {"name": "Vice-Chancellor"},
    {"name": "Proctor / Faculty Advisor"},
    {"name": "Student"},
    {"name": "Employer"},
]

# --- Regulations and their approval history -------------------------------------------
REGULATIONS = [
    {"name": "B.Tech. Degree Programme Regulations 2008, FFCS Regulations - Version 1.00",
     "version": "1.00"},
    {"name": "FFCS Regulations Version 1.10", "version": "1.10"},
    {"name": "FFCS Regulations Version 2.00", "version": "2.00"},
    {"name": "FFCS Regulations Version 2.10", "version": "2.10"},
    {"name": "FFCS Regulations 3.0", "version": "3.0"},
    {"name": "FFCS Academic Regulations 3.1", "version": "3.1"},
    {"name": "FFCS Academic Regulations 3.2", "version": "3.2"},
    {"name": "FFCS Academic Regulations Version 4.0", "version": "4.0",
     "applicable_from": "2021-22",
     "incorporates_changes_till": "71st Academic Council meeting",
     "is_current": True},
    {"name": "VIT Business School Regulations", "version": "separate"},
]

COUNCIL_MEETINGS = [
    {"number": 18, "name": "18th Academic Council meeting", "date": "16 July 2009",      "date_known": True},
    {"number": 20, "name": "20th Academic Council meeting", "date": "26 March 2010",     "date_known": True},
    {"number": 27, "name": "27th Academic Council meeting", "date": "27 July 2012",      "date_known": True},
    {"number": 28, "name": "28th Academic Council meeting", "date": "15 August 2012",    "date_known": True},
    {"number": 37, "name": "37th Academic Council meeting", "date": "16 June 2015",      "date_known": True},
    {"number": 46, "name": "46th Academic Council meeting", "date": "24 August 2017",    "date_known": True},
    {"number": 59, "name": "59th Academic Council meeting", "date": "24 September 2020", "date_known": True},
    # Referenced only as the cut-off for changes folded into v4.0, so it carries no
    # APPROVED_IN edge; v4.0 records it as the `incorporates_changes_till` property.
    {"number": 71, "name": "71st Academic Council meeting", "date": None, "date_known": False,
     "note": "referenced as the cut-off for changes incorporated into version 4.0"},
    # The source prints the date literally as a row of x characters. Not invented.
    {"number": 72, "name": "72nd Academic Council meeting", "date": "xxxxxxxxxxxxxxx",
     "date_known": False},
    {"number": None, "name": "Standing Committee meeting of the Academic Council",
     "date": "24 September 2010", "date_known": True},
]

APPROVED_IN = [
    ("1.00", "18th Academic Council meeting"),
    ("1.10", "20th Academic Council meeting"),
    ("2.00", "27th Academic Council meeting"),
    ("2.10", "28th Academic Council meeting"),
    ("3.0",  "37th Academic Council meeting"),
    ("3.1",  "46th Academic Council meeting"),
    ("3.2",  "59th Academic Council meeting"),
    ("4.0",  "72nd Academic Council meeting"),
    ("separate", "Standing Committee meeting of the Academic Council"),
]

# Newest supersedes next-newest, back to the first version.
SUPERSEDES = [("4.0", "3.2"), ("3.2", "3.1"), ("3.1", "3.0"),
              ("3.0", "2.10"), ("2.10", "2.00"), ("2.00", "1.10"), ("1.10", "1.00")]

CONVENED_BY = [
    ("18th Academic Council meeting", "Academic Council"),
    ("20th Academic Council meeting", "Academic Council"),
    ("27th Academic Council meeting", "Academic Council"),
    ("28th Academic Council meeting", "Academic Council"),
    ("37th Academic Council meeting", "Academic Council"),
    ("46th Academic Council meeting", "Academic Council"),
    ("59th Academic Council meeting", "Academic Council"),
    ("71st Academic Council meeting", "Academic Council"),
    ("72nd Academic Council meeting", "Academic Council"),
    ("Standing Committee meeting of the Academic Council",
     "Standing Committee of the Academic Council"),
]

# --- Systems, concepts, features, baskets ---------------------------------------------
SYSTEMS = [
    {"name": "FFCS", "full_name": "Fully Flexible Credit System", "introduced_year": 2008,
     "kind": "system"},
    {"name": "VTOP", "full_name": "VIT on Top", "kind": "system",
     "note": "academic software of VIT; project/internship submissions and all academic "
             "operations are performed through it"},
]

CONCEPTS = [
    {"name": "CAL",  "full_name": "Curriculum for Applied Learning"},
    {"name": "PBL",  "full_name": "Project Based Learning"},
    {"name": "ICT",  "full_name": "Information and Communication Technology"},
    {"name": "LTPC", "full_name": "Lecture Tutorial Practical Credits"},
    {"name": "TH",   "full_name": "Theory Only Courses"},
    {"name": "LO",   "full_name": "Lab only courses"},
    {"name": "CO",   "full_name": "Course Outcomes"},
    {"name": "Slot-based time table",
     "full_name": "Slot-based time table allowing a student to choose class timings"},
]

COURSE_BASKETS = [
    {"name": "Foundation Core", "abbr": "FC"},
    {"name": "Discipline Linked Engineering Courses", "abbr": "DLE"},
    {"name": "Discipline Core", "abbr": "DC"},
    {"name": "Discipline Elective", "abbr": "DE"},
    {"name": "Specialization Elective", "abbr": "SE"},
    {"name": "Open Elective", "abbr": "OE"},
    {"name": "Skill Enhancement Courses", "abbr": "SEC"},
    {"name": "Ability Enhancement Courses", "abbr": "AEC"},
    {"name": "Project and Internship", "abbr": None},
]

FEATURES = [
    (0,  "Students can register courses of their choice and alter the pace of learning within the broad framework of academic course and credit requirements."),
    (1,  "FFCS allows the students to decide their academic plan and permits students to alter it as they progress in time."),
    (2,  "Slot-based time table is followed. Under this, a student will be able to choose the time he/she wants to attend a theory class/lab."),
    (3,  "Students can make their own time table and each student in a class may have a different timetable of his/her own."),
    (4,  "Students apply the course principles by using analytical and critical thinking and thus have an opportunity to carry out challenging project(s) as part of the curriculum."),
    (5,  "Students have the option of choosing courses from a 'basket of courses' that are grouped into Foundation Core, Discipline Linked Engineering Courses, Discipline Core, Discipline Elective or Specialization Elective, Open Elective, Skill Enhancement Courses, Ability Enhancement Courses and Project and Internship."),
    (6,  "Students can choose courses from the other programmes (interdisciplinary courses) which will help the student to develop additional skills."),
    (7,  "Important courses are offered in both semesters, which will help the students to re-register the course and clear the backlog in the subsequent semester. This will help the slow learners."),
    (8,  "Provisions are there for academically sound students to carry out research activities in their UG Programme."),
    (9,  "FFCS offers not only wide choice of courses for students to build their own curriculum, but also enhances their skill in planning."),
    (10, "A Proctor / faculty advisor helps the student in identifying the courses to be studied in each semester based on programme requirement, course prerequisites, student's academic ability and interest in various disciplines, past academic history, proposed course offerings and other related criteria."),
]

# Feature 5 is the one that enumerates the baskets.
FEATURE_REFERS_TO = [(5, basket["name"]) for basket in COURSE_BASKETS]

ABBREVIATIONS = [
    # (short, expansion, target label, target name)
    ("DLE",  "Discipline Linked Engineering Courses", "CourseBasket", "Discipline Linked Engineering Courses"),
    ("DE",   "Discipline Elective",                   "CourseBasket", "Discipline Elective"),
    ("SE",   "Specialization Elective",               "CourseBasket", "Specialization Elective"),
    ("OE",   "Open Elective",                         "CourseBasket", "Open Elective"),
    ("SEC",  "Skill Enhancement Courses",             "CourseBasket", "Skill Enhancement Courses"),
    ("AEC",  "Ability Enhancement Courses",           "CourseBasket", "Ability Enhancement Courses"),
    ("DC",   "Discipline Core",                       "CourseBasket", "Discipline Core"),
    ("FC",   "Foundation core",                       "CourseBasket", "Foundation Core"),
    ("LTPC", "Lecture Tutorial Practical Credits",    "Concept",      "LTPC"),
    ("TH",   "Theory Only Courses",                   "Concept",      "TH"),
    ("LO",   "Lab only courses",                      "Concept",      "LO"),
    ("CO",   "Course Outcomes",                       "Concept",      "CO"),
    ("FFCS", "Fully Flexible Credit System",          "System",       "FFCS"),
    ("PBL",  "Project Based Learning",                "Concept",      "PBL"),
    ("CAL",  "Curriculum for Applied Learning",       "Concept",      "CAL"),
    ("ICT",  "Information and Communication Technology", "Concept",   "ICT"),
    ("VTOP", "VIT on Top",                            "System",       "VTOP"),
]

# --- Schools, programmes, exams, admission --------------------------------------------
SCHOOLS = [
    {"name": "VIT School of Design", "alias": "V-SIGN", "functional_from": "July 2018",
     "discipline": "Industrial Design", "campus": "VIT Vellore"},
    {"name": "VIT Business School", "alias": None, "campus": None,
     "note": "programmes are governed by separate Regulations"},
]

FACILITIES = [
    {"name": "PROTICS Studio", "detail": "PROduct aestheTICS"},
    {"name": "3D-iD Studio", "detail": "equipped with 30 iMacs"},
    {"name": "Smart PD Lab", "detail": None},
    {"name": "Ergonomics Lab", "detail": None},
    {"name": "Painting Booth", "detail": None},
]

# STATED  -> the document gives the admission route
# NOT_STATED_IN_SOURCE -> the document does not state it at all
PROGRAMMES = [
    {"name": "B.Tech CSE", "level": "UG", "discipline": "Computer Science and Engineering",
     "aliases": ["BTech CSE", "B.Tech. CSE"], "admission_information_status": "STATED"},
    {"name": "B.Tech EEE", "level": "UG", "discipline": "Electrical and Electronics Engineering",
     "aliases": ["BTech EEE"], "admission_information_status": "STATED"},
    {"name": "B.Tech ECE", "level": "UG", "discipline": "Electronics and Communication Engineering",
     "aliases": ["BTech ECE"], "admission_information_status": "STATED"},
    {"name": "B.Tech Civil", "level": "UG", "discipline": "Civil Engineering",
     "aliases": ["BTech Civil"], "admission_information_status": "STATED"},
    {"name": "B.Tech Mechanical", "level": "UG", "discipline": "Mechanical Engineering",
     "aliases": ["BTech Mechanical", "B.Tech Mechnical"], "admission_information_status": "STATED"},
    {"name": "B.Tech Fashion Technology", "level": "UG", "discipline": "Fashion Technology",
     "aliases": ["BTech Fashion Technology", "B.Tech.Fashion Technology"],
     "admission_information_status": "STATED"},
    {"name": "M.Tech", "level": "PG", "duration_years": 2, "aliases": ["MTech", "M.Tech."],
     "admission_information_status": "STATED"},
    {"name": "B.Des", "level": "UG", "discipline": "Industrial Design", "aliases": ["BDes"],
     "admission_information_status": "STATED"},
    {"name": "M.Des", "level": "PG", "discipline": "Industrial Design", "aliases": ["MDes"],
     # No ADMITS_VIA and no REQUIRES edge: the document never states this route, so the
     # graph asserts nothing. The status property records WHY it is absent, which lets a
     # query answer "the document does not say" rather than returning a bare empty result.
     "admission_information_status": "NOT_STATED_IN_SOURCE",
     "status_reason": "source document truncated mid-sentence on page 3"},
]

ENTRANCE_EXAMS = [
    {"name": "VITEEE", "full_name": "VIT Engineering Entrance Exam",
     "mode": "national level computer based competitive examination",
     "frequency": "once a year", "months": "April-May",
     "announced_via": ["media", "university website"]},
    {"name": "VITMEE", "full_name": "VIT Master's Entrance Exam",
     "mode": "national level computer based competitive examination",
     "frequency": "once a year", "months": "April-May",
     "announced_via": ["media", "university website"]},
    {"name": "UCEED", "full_name": "Undergraduate Common Entrance Exam for Design"},
    {"name": "V-DAT", "full_name": "Design Aptitude Test"},
]

CONDUCTED_BY = [("VITEEE", "VIT University"), ("VITMEE", "VIT University")]

BTECH_VITEEE = ["B.Tech CSE", "B.Tech EEE", "B.Tech ECE", "B.Tech Civil", "B.Tech Mechanical"]

# (programme, exam, properties)
ADMITS_VIA = (
    [(p, "VITEEE", {}) for p in BTECH_VITEEE]
    + [("M.Tech", "VITMEE", {
        "source_note": "The source paragraph inconsistently says students are admitted "
                       "'based on their VITEEE ranks'; VITMEE is the M.Tech entrance "
                       "exam. The graph stores the intended fact and keeps the source "
                       "wording here, so the correction is recorded rather than hidden."})]
    + [("B.Des", "UCEED", {"condition_group": "OR_1"}),
       ("B.Des", "V-DAT", {"condition_group": "OR_1"})]
)

# Explicit negative knowledge.
#
# The document says of this programme: "There is NO Entrance Examination." That is a
# positive assertion about a negative fact, so it is stored as an edge rather than as
# a missing edge. A missing edge would be ambiguous: M.Des also has no ADMITS_VIA edge,
# but for a completely different reason (the source is truncated). Under the open-world
# assumption, absence alone cannot distinguish "no exam required" from "not stated".
EXEMPT_FROM = [("B.Tech Fashion Technology", "VITEEE", {
    "evidence": "There is NO Entrance Examination.",
    "source_page": 3})]

ADMISSION_CRITERIA = [
    {"name": "VITEEE rank",       "kind": "exam rank"},
    {"name": "VITMEE rank",       "kind": "exam rank"},
    {"name": "UCEED score",       "kind": "exam score"},
    {"name": "V-DAT score",       "kind": "exam score"},
    {"name": "10+2 marks",        "kind": "qualifying examination marks"},
    {"name": "subject of study",  "kind": "qualifying examination subject"},
    {"name": "merit list",        "kind": "selection process"},
    {"name": "counselling",       "kind": "selection process"},
    {"name": "seat availability", "kind": "constraint"},
    {"name": "work experience",   "kind": "preference"},
]

# (programme, criterion, properties)
# condition_group "OR_n" -> alternatives, satisfying any one satisfies the group.
# condition_group "AND"  -> individually required.
#
# B.Des needs (UCEED OR V-DAT) AND 10+2 marks. Three flat edges would assert that a
# candidate needs all three, which is false and would wrongly reject a UCEED-only
# applicant. This property is the minimum machinery that keeps the logic honest.
REQUIRES = (
    [(p, "VITEEE rank", {"condition_group": "AND", "mandatory": True}) for p in BTECH_VITEEE]
    + [(p, "counselling", {"condition_group": "AND", "mandatory": True,
                           "note": "counselling to choose the preferred campus"})
       for p in BTECH_VITEEE]
    + [
        ("B.Tech Fashion Technology", "10+2 marks",       {"condition_group": "AND", "mandatory": True, "note": "merit list is prepared on this basis"}),
        ("B.Tech Fashion Technology", "subject of study", {"condition_group": "AND", "mandatory": True, "note": "merit list is prepared on this basis"}),
        ("B.Tech Fashion Technology", "merit list",       {"condition_group": "AND", "mandatory": True}),
        ("B.Tech Fashion Technology", "counselling",      {"condition_group": "AND", "mandatory": True, "note": "virtual or physical; does not guarantee admission"}),
        ("B.Tech Fashion Technology", "seat availability",{"condition_group": "AND", "mandatory": True, "note": "number of seats and mode of selection at the discretion of the Management"}),

        ("M.Tech", "VITMEE rank",    {"condition_group": "AND", "mandatory": True}),
        ("M.Tech", "counselling",    {"condition_group": "AND", "mandatory": True}),
        ("M.Tech", "work experience",{"condition_group": "AND", "mandatory": False, "note": "an added advantage, not a requirement"}),

        # (UCEED OR V-DAT) AND 10+2 marks - see the condition_group note above.
        ("B.Des", "UCEED score", {"condition_group": "OR_1", "mandatory": True}),
        ("B.Des", "V-DAT score", {"condition_group": "OR_1", "mandatory": True}),
        ("B.Des", "10+2 marks",  {"condition_group": "AND",  "mandatory": True,
                                  "note": "in the qualifying examination"}),
        # M.Des deliberately absent: the source does not state its admission route.
    ]
)

OFFERS = [("VIT School of Design", "B.Des"), ("VIT School of Design", "M.Des")]
HAS_FACILITY = [("VIT School of Design", f["name"]) for f in FACILITIES]
ADVISES = [("Proctor / Faculty Advisor", "Student")]
