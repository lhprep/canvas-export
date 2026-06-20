import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pprint import pprint

from canvasapi import Canvas
from tqdm import tqdm

basepath = "."
folder = ""
selected_terms = [532]

class Worker(threading.Thread):
    def __init__(self, q, pb, *args, **kwargs):
        self.q = q
        self.pb = pb
        super().__init__(*args, **kwargs)

    def run(self):
        while True:
            try:
                filename, url = self.q.get(timeout=3)  # 3s timeout

                if not filename and not url:
                    self.q.task_done()
                    return

                # print("Start " + filename)
                subprocess.run(["curl", "-Lo", filename, "--create-dirs", url],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.q.task_done()
                pb.update()
                # print("End " + filename)
            except queue.Empty:
                time.sleep(1)


# Start Main Script
canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))

all_terms = canvas.get_account(1).get_enrollment_terms()
courses = []

for t_id in selected_terms:
    t = canvas.get_account(1).get_enrollment_term(t_id)
    print(t)
    for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id, include=["term"]):
        courses.append((course, t))

pprint(courses)
print(len(courses))

# exit(0)  # TODO: Remove

exports = []
completed = []

q = queue.Queue()

print("\n\n\nStarting Exports")
with tqdm(total=len(courses)) as pb:
    for course, term in courses:
        exports.append((course, course.export_content("common_cartridge", skip_notifications=True), term))
        pb.update()

print("\n\n\nDownloading")
with tqdm(total=len(courses)) as pb:
    for _ in range(10):
        Worker(q, pb).start()

    while len(completed) < len(exports):
        for course, export, term in exports:
            if export not in completed:
                progress = canvas.get_progress(export.progress_url.split("/")[-1])
                if progress.workflow_state == "completed":
                    x = course.get_content_export(export)
                    filename = f"{course.sis_course_id + ' - ' if course.sis_course_id else ''}{course.name}.zip"
                    filename = filename.replace("/", "-")
                    filename = f"{basepath}/{folder}/{term.name.replace("/", "-")}/{filename}"
                    # print(filename)

                    q.put_nowait((filename, x.attachment.get("url")))

                    completed.append(export)

    for _ in range(10):
        q.put_nowait(("", ""))

    q.join()
