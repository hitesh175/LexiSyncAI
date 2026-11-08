"""Measure citation regions against PDFplumber's independent text coordinates."""
import csv
from pathlib import Path
import re

import numpy as np
import pdfplumber
from PIL import Image, ImageDraw

from preview import render_citation

ROOT = Path(__file__).resolve().parent
SAMPLES = [
    ("data/17-USC-106.pdf", 1, "to prepare derivative works based upon the copyrighted work"),
    ("data/17-USC-106.pdf", 1, "the public by sale or other transfer of ownership"),
    ("data/17-USC-107.pdf", 1, "the nature of the copyrighted work"),
    ("data/17-USC-107.pdf", 1, "the effect of the use upon the potential market"),
    ("rehearsal/17-USC-Chapter-2.pdf", 1, "The authors of a joint work are coowners of copyright in the work."),
    ("rehearsal/17-USC-Chapter-2.pdf", 6, "signed by the owner of the rights conveyed"),
    ("01-EU-GDPR-Regulation-2016-679.pdf", 37, "It shall be as easy to withdraw as to give consent."),
    ("01-EU-GDPR-Regulation-2016-679.pdf", 52, "The processor shall notify the controller without undue delay after becoming aware of a personal data breach."),
    ("01-EU-GDPR-Regulation-2016-679.pdf", 82, "2 % of the total worldwide annual turnover"),
    ("03-EDPB-Breach-Notification.pdf", 11, "a reasonable degree of certainty that a security incident has occurred"),
]


def evaluate(filename, page_number, quote):
    file = ROOT / filename
    content = file.read_bytes()
    rendered, marked = render_citation(content, page_number, quote)
    plain, _ = render_citation(content, page_number, "")
    with pdfplumber.open(file) as pdf:
        page = pdf.pages[page_number - 1]
        pattern = r"\s+".join(re.escape(word) for word in quote.split())
        matches = page.search(pattern) or []
        if not matches and filename.startswith(("data/", "rehearsal/")):
            half = page.width / 2
            matches = [match for left, right in ((0, half), (half, page.width))
                       for match in page.crop((left, 0, right, page.height)).search(pattern)]
        scale_x = rendered.width / page.width
        scale_y = rendered.height / page.height
        gold = Image.new("1", rendered.size)
        brush = ImageDraw.Draw(gold)
        for match in matches:
            # Separate lines rather than covering the whitespace between them.
            lines = {}
            for char in match["chars"]:
                if char["text"].strip():
                    lines.setdefault(round(char["top"] / 3), []).append(char)
            for chars in lines.values():
                brush.rectangle((min(c["x0"] for c in chars) * scale_x,
                                 min(c["top"] for c in chars) * scale_y,
                                 max(c["x1"] for c in chars) * scale_x,
                                 max(c["bottom"] for c in chars) * scale_y), fill=1)
    observed = np.any(np.asarray(rendered) != np.asarray(plain), axis=2)
    expected = np.asarray(gold)
    overlap = (observed & expected).sum()
    precision = round(float(overlap / observed.sum()), 3) if observed.any() and len(matches) == 1 else ""
    coverage = round(float(overlap / expected.sum()), 3) if expected.any() and len(matches) == 1 else ""
    outcome = ("full-page fallback" if not marked else
               "correct region" if len(matches) == 1 and precision >= .5 and coverage >= .5 else
               "wrong or ambiguous region")
    box = gold.getbbox()
    if box:
        left, top, right, bottom = box
        crop = rendered.crop((max(0, left-18), max(0, top-20),
                              min(rendered.width, right+18), min(rendered.height, bottom+20)))
    else:
        crop = rendered.copy()
        crop.thumbnail((540, 90))
    crop.thumbnail((560, 110))
    return (filename, page_number, quote, len(matches), outcome, precision, coverage), crop


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("region-results"))
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    rows, crops = zip(*(evaluate(*sample) for sample in SAMPLES))
    with (output / "regions.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "pdf_page", "quote", "reference_matches", "outcome",
                         "pixel_precision", "reference_pixel_coverage"])
        writer.writerows(rows)
    review = Image.new("RGB", (1200, 700), "#f8f8f2")
    label = ImageDraw.Draw(review)
    for i, (row, crop) in enumerate(zip(rows, crops), 1):
        x, y = ((i-1) % 2) * 600 + 12, ((i-1) // 2) * 140 + 10
        label.text((x, y), f"{i}. PDF page {row[1]} | {row[4]} | overlap {row[5]}", fill="#20362e")
        review.paste(crop.convert("RGB"), (x, y + 22))
    review.save(output / "region-review.png")
    for i, row in enumerate(rows, 1):
        print(i, row[3:])


if __name__ == "__main__":
    main()

