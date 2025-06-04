import os
import queue
import subprocess
import threading
import time

from canvasapi import Canvas
from tqdm import tqdm


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

terms = canvas.get_account(1).get_enrollment_terms()
courses = []

folder = "all"

for course in canvas.get_account(1).get_courses(include=["term"]):
    courses.append(course)

print(f"Getting {len(courses)} courses")
# exit(0)  # TODO: Remove

exports = []
completed = []

q = queue.Queue()

print("\n\n\nStarting Exports")
with tqdm(total=len(courses)) as pb:
    for course in courses:
        term_dir = os.path.join("./canvas-exports", folder, course.term['name'].replace("/","-"))
        os.makedirs(term_dir, exist_ok=True)

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
                    filename = f"{course.sis_course_id + ' - ' if course.sis_course_id else ''}{course.name}.zip"
                    filename = filename.replace("/", "-")
                    filename = os.path.join("./canvas-exports", folder, course.term['name'].replace("/","-"), filename)
                    # print(filename)

                    q.put_nowait((filename, x.attachment.get("url")))

                    completed.append(export)

    for _ in range(10):
        q.put_nowait(("", ""))

    q.join()
