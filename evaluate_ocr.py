"""Evaluate local OCR on rasterized, originally searchable public PDFs."""
from contextlib import closing
import csv
from io import BytesIO
from pathlib import Path
import re
from time import perf_counter
import unicodedata

import pdfplumber
import pypdfium2 as pdfium

from lexic import ingest
from scan_ocr import read_scan

ROOT = Path(__file__).resolve().parent
SAMPLES = (
    ("01-EU-GDPR-Regulation-2016-679.pdf", 37),
    ("01-EU-GDPR-Regulation-2016-679.pdf", 52),
    ("03-EDPB-Breach-Notification.pdf", 11),
)


def words(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "").casefold()
    return re.findall(r"[^\W_]+", text)


def edits(expected, actual):
    row = list(range(len(actual) + 1))
    for i, term in enumerate(expected, 1):
        next_row = [i]
        for j, observed in enumerate(actual, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1, row[j-1] + (term != observed)))
        row = next_row
    return row[-1]


def rasterize(path, page_number):
    with closing(pdfium.PdfDocument(path)) as pdf, closing(pdf[page_number - 1]) as page:
        with closing(page.render(scale=2.2)) as bitmap:
            image = bitmap.to_pil().convert("RGB")
    output = BytesIO()
    image.save(output, format="PDF", resolution=158.4)
    return output.getvalue()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation-results" / "ocr-evaluation")
    directory = parser.parse_args().output
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename, number in SAMPLES:
        path = ROOT / filename
        with pdfplumber.open(path) as pdf:
            expected = words(pdf.pages[number - 1].extract_text() or "")
        sample = {f"rasterized-page-{number}.pdf": rasterize(path, number)}
        without_ocr, before = ingest(sample)
        assert not without_ocr and before[0]["image_only"]
        started = perf_counter()
        def capture(content, page_number):
            nonlocal recognized
            recognized = read_scan(content, page_number)
            return recognized
        recognized = ""
        passages, after = ingest(sample, ocr_reader=capture)
        elapsed = perf_counter() - started
        assert passages and all(p.ocr for p in passages), after
        actual = words(recognized)
        errors = edits(expected, actual)
        rows.append((filename, number, len(expected), len(actual), errors,
                     round(errors / len(expected), 4), round(elapsed, 2),
                     before[0]["ocr_status"], after[0]["ocr_status"]))
        print(rows[-1], flush=True)
    with (directory / "ocr-sample.csv").open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["source_pdf", "source_page", "reference_words", "ocr_words", "word_edits",
                         "word_error_rate", "recognition_and_ingestion_seconds", "without_ocr", "with_ocr"])
        writer.writerows(rows)
    print("Aggregate WER:", sum(r[4] for r in rows) / sum(r[2] for r in rows))


if __name__ == "__main__":
    main()
