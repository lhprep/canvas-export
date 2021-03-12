import os
import time

from canvasapi import Canvas

canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

for t in terms:
    break
    if "2019/2020" in str(t):
        print(t)
        for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id):
            courses.append(course)

print(courses)
print(len(courses))

course = canvas.get_course(8537)

export = course.export_content("zip", skip_notifications=True)
print(export)

while True:
    progress = canvas.get_progress(export.progress_url.split("/")[-1])
    if progress.workflow_state == "completed": break
    print(progress.completion)
    time.sleep(1)

export = course.get_content_export(export)
print(export.attachment.get("url"))
