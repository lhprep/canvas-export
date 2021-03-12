import os
import time
import subprocess

from pprint import pprint as print

from canvasapi import Canvas

canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

file_prefix = "2019/2020"

for t in terms:
    if "2019/2020" in str(t) and "6th - Quarter 1" in str(t):
        print(t)
        for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id, include=["term"]):
            courses.append(course)

print(courses)
print(len(courses))

# exit(0)  # TODO: Remove

exports = []
completed = []

for course in courses:
    exports.append((course, course.export_content("zip", skip_notifications=True)))

while len(completed) < len(exports):
    progresses = []
    for course, export in exports:
        if export not in completed:
            progress = canvas.get_progress(export.progress_url.split("/")[-1])
            progresses.append(str(progress.completion))
            if progress.workflow_state == "completed":
                export = course.get_content_export(export)
                filename = f"{course.sis_course_id if course.sis_course_id else file_prefix} - {course.name}.zip"
                filename = filename.replace("/", "~")
                subprocess.run(["curl", "-o", filename, export.attachment.get("url")])
                completed.append(export)

    print(" ".join(progresses))
    print(" ".join(completed))
    time.sleep(1)
