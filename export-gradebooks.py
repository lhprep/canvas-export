import csv
import json
import os
from datetime import datetime, timezone

from canvasapi import Canvas
from tqdm import tqdm

canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN", ""))

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

folder = "."
start = datetime(2025, 7, 1, tzinfo=timezone.utc)
end = datetime(2026, 7, 1, tzinfo=timezone.utc)
school = "MS"
skip_dates = False
dump_raw = True

for t in terms:
    if school in str(t) and (skip_dates or (t.start_at_date > start and t.end_at_date < end)):
        print(t)
        for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id, include=["term"]):
            courses.append(course)

# pprint(courses)
# print(len(courses))


def safe(s):
    return (s or "").replace("/", "~").replace("\\", "~")


def to_dict(obj):
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {
            k: to_dict(v)
            for k, v in vars(obj).items()
            if not k.startswith("_") and not k.endswith("_date")
        }
    return obj


def cell_value(sub):
    # Mirrors Canvas's not_placeholder scope; everything else is a true placeholder.
    if getattr(sub, "excused", False):
        return "EX"
    score = getattr(sub, "score", None)
    if score is not None:
        return f"{score:g}"
    if getattr(sub, "submission_type", None) is not None:
        return ""  # submitted but ungraded
    if getattr(sub, "workflow_state", None) == "graded":
        return ""  # graded with no score (rare)
    return None  # placeholder, skip


print("\n\n\nStarting Exports")
with tqdm(total=len(courses)) as pb:
    for course in courses:
        pb.set_description(course.name[:40])

        assignments = [a for a in course.get_assignments() if getattr(a, "published", False)]
        assignments.sort(key=lambda a: (getattr(a, "position", 0) or 0, a.id))
        assignment_cols = [
            (a.id, a.name, getattr(a, "points_possible", None)) for a in assignments
        ]

        enrollments = list(course.get_enrollments(
            type=["StudentEnrollment"],
            state=["active", "invited", "completed"],
            include=["user"],
        ))

        students = {}  # user_id -> {"name": ..., "sis": ...}
        for e in enrollments:
            uid = e.user_id
            if uid in students:
                continue
            user = getattr(e, "user", {}) or {}
            students[uid] = {
                "name": user.get("sortable_name") or user.get("name") or str(uid),
                "sis": user.get("sis_user_id") or "",
            }

        grades = {}  # user_id -> {assignment_id: cell}
        raw_submissions = []
        for a in tqdm(assignments, desc=course.name[:40], leave=False):
            sub_kwargs = {}
            if dump_raw:
                sub_kwargs["include"] = ["submission_comments", "rubric_assessment", "user"]
            for sub in a.get_submissions(**sub_kwargs):
                v = cell_value(sub)
                if v is not None:
                    grades.setdefault(sub.user_id, {})[a.id] = v
                if dump_raw:
                    raw_submissions.append(to_dict(sub))

        # Include any grade-only students not in the enrollments call (rare but possible)
        for uid in grades:
            students.setdefault(uid, {"name": str(uid), "sis": ""})

        # Drop assignments where no student has a real grade (numeric or EX).
        graded_aids = {aid for row in grades.values() for aid, v in row.items() if v != ""}
        assignment_cols = [col for col in assignment_cols if col[0] in graded_aids]

        term_name = (course.term or {}).get("name", "") if isinstance(course.term, dict) else ""
        filename = safe(f"{term_name} - {course.name}").strip(" -") + ".csv"
        path = os.path.join(folder, filename)

        def header(name, possible):
            return f"{name} (out of {possible:g})" if possible is not None else name

        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["Student", "SIS ID"]
                + [header(name, p) for _, name, p in assignment_cols]
                + ["Total Earned", "Total Possible"]
            )
            for uid in sorted(students, key=lambda u: students[u]["name"].lower()):
                row = grades.get(uid, {})
                cells = [row.get(aid, "") for aid, _, _ in assignment_cols]
                earned = sum(float(c) for c in cells if c not in ("", "EX"))
                possible = sum(
                    (p or 0)
                    for (_, _, p), c in zip(assignment_cols, cells)
                    if c != "EX"
                )
                w.writerow(
                    [students[uid]["name"], students[uid]["sis"]]
                    + cells
                    + [f"{earned:g}", f"{possible:g}"]
                )

        if dump_raw:
            json_path = path[:-4] + ".json"
            payload = {
                "course": {
                    "id": course.id,
                    "name": course.name,
                    "sis_course_id": getattr(course, "sis_course_id", None),
                    "term": course.term if isinstance(course.term, dict) else None,
                },
                "assignments": [to_dict(a) for a in assignments],
                "students": [
                    {"user_id": uid, "name": s["name"], "sis": s["sis"]}
                    for uid, s in students.items()
                ],
                "enrollments_raw": [to_dict(e) for e in enrollments],
                "submissions": raw_submissions,
            }
            with open(json_path, "w") as f:
                json.dump(payload, f, default=str)

        pb.update()