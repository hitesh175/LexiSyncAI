"""Compare extracted table cells with manually transcribed source values."""
import csv
from pathlib import Path
import re

import pdfplumber

from tables import table_cells

ROOT = Path(__file__).resolve().parent


def normalize(value):
    value = value.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", re.sub(r"\s*-\s*", "-", value)).strip()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation-results" / "table-evaluation" / "results.csv")
    args = parser.parse_args()
    with (ROOT / "table-evaluation" / "gold.psv").open(encoding="utf-8-sig") as stream:
        gold = list(csv.DictReader(stream, delimiter="|"))
    with pdfplumber.open(ROOT / "02-EDPB-Administrative-Fines.pdf") as pdf:
        extracted = {
            (number, table_number, cell.row, ",".join(map(str, cell.columns))): cell
            for number in {int(row["page"]) for row in gold}
            for table_number, table in enumerate(pdf.pages[number - 1].find_tables(), 1)
            for cell in table_cells(table)
        }
    results = []
    fields = ("row_label", "column_label", "value")
    for row in gold:
        key = tuple(map(int, (row["page"], row["table"], row["row"]))) + (row["columns"],)
        cell = extracted.get(key)
        result = dict(row, found=bool(cell))
        for field in fields:
            actual = getattr(cell, field, "")
            result[f"observed_{field}"] = actual
            result[f"{field}_correct"] = bool(cell and normalize(actual) == normalize(row[field]))
        results.append(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    for field in ("found", *(f"{field}_correct" for field in fields)):
        print(f"{field}: {sum(row[field] for row in results)}/{len(results)}")
    for row in results:
        if not all(row[f"{field}_correct"] for field in fields):
            print("Mismatch:", row)


if __name__ == "__main__":
    main()
