import os
import queue
import threading
import time
import subprocess

from pprint import pprint

import requests
from canvasapi import Canvas
from tqdm import tqdm


class Worker(threading.Thread):
    def __init__(self, q, pb, *args, **kwargs):
        self.q = q
        self.pb = pb
        self.sleep_counter = 0
        super().__init__(*args, **kwargs)

    def run(self):
        while True:
            try:
                filename, url = self.q.get(timeout=3)  # 3s timeout
                self.sleep_counter = 0

                print("Start " + filename)
                subprocess.run(["curl", "-Lo", filename, url],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.q.task_done()
                pb.update()
                print("End " + filename)
            except queue.Empty:
                if self.sleep_counter >= 6:
                    print("***** THREAD DIED *****")
                    return
                else:
                    self.sleep_counter += 1
                    time.sleep(5)


# Start Main Script
canvas = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

file_prefix = "2019-2020"

for t in terms:
    if "2020/2021" in str(t) and "6th" in str(t):
        pprint(t)
        for course in canvas.get_account(1).get_courses(enrollment_term_id=t.id, include=["term"]):
            courses.append(course)

pprint(courses)
print(len(courses))

# exit(0)  # TODO: Remove

exports = []
completed = []

q = queue.Queue()

print("\n\n\nStarting Exports")
with tqdm(total=len(courses)) as pb:
    for course in courses:
        exports.append((course, course.export_content("common_cartridge", skip_notifications=True)))
        pb.update()

print("\n\n\nDownloading")
with tqdm(total=len(courses)) as pb:
    for _ in range(10):
        Worker(q, pb).start()

    while len(completed) < len(exports):
        for course, export in exports:
            if export not in completed:
                progress = canvas.get_progress(export.progress_url.split("/")[-1])
                if progress.workflow_state == "completed":
                    x = course.get_content_export(export)
                    filename = f"{course.sis_course_id if course.sis_course_id else file_prefix} - {course.name}.zip"
                    filename = filename.replace("/", "~")

                    q.put_nowait((filename, x.attachment.get("url")))

                    completed.append(export)

    q.join()
