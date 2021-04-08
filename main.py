import os
import time
import subprocess

from pprint import pprint as print

from canvasapi import Canvas
from tqdm import tqdm

canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

file_prefix = "2019/2020"

for t in terms:
    if "2020/2021" in str(t) and "6th" in str(t):
        print(t)
        for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id, include=["term"]):
            courses.append(course)

print(courses)
print(len(courses))

# exit(0)  # TODO: Remove

exports = []
completed = []

print("\n\n\nStarting Exports")
with tqdm(total=len(courses)) as pb:
    for course in courses:
        exports.append((course, course.export_content("common_cartridge", skip_notifications=True)))
        pb.update()

print("\n\n\nDownloading")
with tqdm(total=len(courses)) as pb:
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
                    subprocess.run(["curl", "-Lo", filename, export.attachment.get("url")],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    completed.append(export)
                    pb.update()

        print(" ".join(progresses))
        time.sleep(1)
