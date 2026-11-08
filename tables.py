"""Preserve the row and column context of cells in ruled PDF tables."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TableCell:
    row: int
    columns: tuple[int, ...]
    row_label: str
    column_label: str
    value: str


def table_cells(table):
    """Resolve headers and row labels through the physical cell rectangles."""
    rows = table.rows
    values = table.extract()
    if len(rows) < 2:
        return []
    leaf_row = max(rows, key=lambda row: sum(box is not None for box in row.cells))
    centers = [(box[0] + box[2]) / 2 for box in leaf_row.cells if box]
    if len(centers) < 2:
        return []

    cells = [
        [(box, " ".join((value or "").split())) for box, value in zip(row.cells, row_values) if box]
        for row, row_values in zip(rows, values)
    ]

    def columns(box):
        return tuple(i for i, x in enumerate(centers) if box[0] <= x < box[2])

    # A top row with text labels is a header. A spanning top row can introduce
    # one additional layer when the next row contains labels instead of values.
    def looks_like_header(items):
        labels = [text for box, text in items if text and any(col > 0 for col in columns(box))]
        return bool(labels) and not any(re.match(r"^[€$£]?\s*\d", text) for text in labels)

    depth = int(looks_like_header(cells[0]))
    if (depth and len(rows) > 2 and looks_like_header(cells[1])
            and any(text and len(columns(box)) > 1 for box, text in cells[0])):
        depth = 2

    headers = [
        " / ".join(dict.fromkeys(text for items in cells[:depth] for box, text in items
                                 if text and column in columns(box))) or f"Column {column + 1}"
        for column in range(len(centers))
    ]

    result = []
    for index, (row, items) in enumerate(zip(rows, cells)):
        if index < depth:
            continue
        y = row.bbox[1] + .01
        row_label = next((text for earlier in cells[:index + 1] for box, text in earlier
                          if text and 0 in columns(box) and box[1] <= y < box[3]), "")
        for box, text in items:
            covered = tuple(col for col in columns(box) if col > 0)
            if not text or not covered:
                continue
            label = " + ".join(dict.fromkeys(headers[col] for col in covered))
            result.append(TableCell(index + 1, tuple(col + 1 for col in covered), row_label, label, text))
    return result


def table_caption(page, table):
    top = table.bbox[1]
    if top <= page.bbox[1]:
        return ""
    region = page.crop((page.bbox[0], max(page.bbox[1], top - 85), page.bbox[2], top))
    for line in reversed((region.extract_text() or "").splitlines()):
        if re.match(r"^(?:Step \d+:|Table \d+\b|Article \d+\s*\()", line.strip(), re.I):
            return line.strip()
    return ""


def table_passages(table, label):
    rows = {}
    for cell in table_cells(table):
        row = f"Row {cell.row}" + (f" ({cell.row_label})" if cell.row_label else "")
        rows.setdefault(cell.row, []).append(
            f"{label} | {row} | Column: {cell.column_label} | Value: {cell.value}"
        )
    if not rows:
        # Preserve extraction for simple tables where a cell grid is unavailable.
        return [[f"{label} | Row {i} | " + " | ".join(" ".join((value or "").split()) for value in values)]
                for i, values in enumerate(table.extract(), 1) if any(values)]
    return rows.values()
