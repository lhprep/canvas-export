import os

from canvasapi import Canvas

c = Canvas("https://lhps.instructure.com/", os.getenv("CANVAS_TOKEN"))
