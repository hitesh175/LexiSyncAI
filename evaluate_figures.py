"""Compare chart answers with and without visual information."""
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageDraw
from figures import read_figure
from preview import render_citation


def chart_page():
    chart = Image.new("RGB", (480, 280), "white")
    draw = ImageDraw.Draw(chart)
    draw.line((65, 230, 415, 230), fill="black", width=3)
    for x, label, height, color in ((100, "A", 70, "royalblue"), (220, "B", 165, "forestgreen"),
                                    (340, "C", 105, "darkorange")):
        draw.rectangle((x, 230 - height, x + 55, 228), fill=color)
        draw.text((x + 23, 238), label, fill="black", font_size=22)
    document = BytesIO()
    chart.save(document, format="PDF")
    page, _ = render_citation(document.getvalue(), 1, "")
    return page


def main():
    page = chart_page()
    control = Image.new("RGB", page.size, "white")
    questions = [
        ("What color is the tallest bar?", "Green"),
        ("What color is the shortest bar?", "Blue"),
        ("Who created the chart?", "Not visible"),
    ]
    runs = []
    for image_available, image in ((False, control), (True, page)):
        for question, expected in questions:
            observed = read_figure(image, question)
            print(image_available, question, observed, flush=True)
            runs.append(dict(image_available=image_available, question=question,
                             expected=expected if image_available else "Not visible", observed=observed))
    output = Path(__file__).resolve().parent / "evaluation-results" / "ablation-evaluation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "figure.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
