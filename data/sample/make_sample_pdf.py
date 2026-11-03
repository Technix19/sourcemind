"""Generate the synthetic sample PDF used for demos and README screenshots.

All content is invented for this project (no real people, studies or data).
Run from apps/api so PyMuPDF is available:
    .venv/bin/python ../../data/sample/make_sample_pdf.py
"""
from pathlib import Path

import pymupdf

PAGES = [
    (
        "Adaptive Practice Platform: Overview",
        "The adaptive practice platform helps learners improve at programming by adjusting the "
        "difficulty of each coding question. The system records correctness, execution time and the "
        "number of attempts for every question a learner answers. These performance signals are "
        "collected during practice sessions and are used to estimate the learner's current level.",
    ),
    (
        "Method",
        "A Random Forest classifier is trained on the performance signals. Its prediction selects "
        "beginner, intermediate or advanced practice for the next question. The classifier was "
        "chosen because it handles small tabular datasets well and gives feature importances that "
        "can be inspected. Training used a synthetic dataset generated for this demonstration.",
    ),
    (
        "Limitations",
        "This is a demonstration document. The synthetic dataset is small and does not represent "
        "real learners, so the results should not be generalised. The platform does not yet "
        "account for learners who guess, and it has not been evaluated against a human tutor.",
    ),
]

doc = pymupdf.open()
for title, body in PAGES:
    page = doc.new_page()
    page.insert_text((72, 90), title, fontsize=18)
    page.insert_textbox(pymupdf.Rect(72, 120, 523, 700), body, fontsize=12)
doc.save(Path(__file__).with_name("adaptive-practice-brief.pdf"))
