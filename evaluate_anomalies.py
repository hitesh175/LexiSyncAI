"""Train and evaluate an autoencoder for unusual page layouts."""
import argparse
import csv
import json
from pathlib import Path
from contextlib import closing

import numpy as np
import pypdfium2 as pdfium
import torch
from torch import nn
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
WIDTH = 24


def page_image(pdf, number):
    with closing(pdf[number - 1]) as page, closing(page.render(scale=.7)) as bitmap:
        return bitmap.to_pil().convert("L").resize((192, 256))


def features(image):
    pixels = np.array(image.resize((WIDTH, WIDTH), Image.Resampling.BOX), dtype=np.float32)
    return torch.from_numpy((1 - pixels / 255).reshape(-1))


def distort(image, variant):
    if variant == "rotated":
        return image.rotate(90, expand=True)
    if variant == "blank":
        return Image.new("L", image.size, 255)
    marked = image.copy()
    ImageDraw.Draw(marked).rectangle((24, 72, 167, 183), fill=0)
    return marked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "anomaly-evaluation")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(42)
    torch.set_num_threads(2)
    with closing(pdfium.PdfDocument(ROOT / "01-EU-GDPR-Regulation-2016-679.pdf")) as pdf:
        train = torch.stack([features(page_image(pdf, page)) for page in range(34, 58)])
        calibration = torch.stack([features(page_image(pdf, page)) for page in range(58, 66)])
        held_out = {page: page_image(pdf, page) for page in range(66, 76)}

    network = nn.Sequential(nn.Linear(WIDTH ** 2, 64), nn.ReLU(), nn.Linear(64, 12),
                            nn.Linear(12, 64), nn.ReLU(), nn.Linear(64, WIDTH ** 2), nn.Sigmoid())
    optimizer = torch.optim.Adam(network.parameters(), lr=.003)
    for _ in range(160):
        optimizer.zero_grad()
        loss = (network(train) - train).square().mean()
        loss.backward()
        optimizer.step()

    def errors(batch):
        with torch.no_grad():
            return (network(batch) - batch).square().mean(dim=1).tolist()

    threshold = max(errors(calibration))
    rows = []
    for number, image in held_out.items():
        for variant in ("clean", "rotated", "blank", "occluded"):
            vector = features(image if variant == "clean" else distort(image, variant))
            error = errors(vector.unsqueeze(0))[0]
            rows.append(dict(pdf_page=number, variant=variant, error=error, flagged=error > threshold))
    with (args.output / "page-scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"threshold": threshold, "train_pages": 24, "calibration_pages": 8, "test_pages": 10,
               "flagged_by_variant": {v: sum(r["flagged"] for r in rows if r["variant"] == v)
                                      for v in ("clean", "rotated", "blank", "occluded")}}
    (args.output / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
