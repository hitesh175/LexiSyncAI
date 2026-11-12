"""Fine-tune a cross-encoder and compare its ranks on fixed held-out candidates."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

import torch
from lexic import Index, ingest, models
from evaluate import covered

ROOT = Path(__file__).resolve().parent


def cases(question_file, paths):
    docs = {p.name: p.read_bytes() for p in paths}
    passages, _ = ingest(docs)
    index = Index(passages)
    with (ROOT / question_file).open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream, delimiter="|"))
    for row in rows:
        gold = {tuple(item.split(":", 2)) for item in row["gold"].split(";") if item}
        if gold:
            yield row["question"], index.retrieve(row["question"], k=20, mode="fusion"), gold


def inputs(tokenizer, question, passages):
    return tokenizer([question] * len(passages), [p.text for p in passages],
                     padding=True, truncation=True, max_length=256, return_tensors="pt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairwise", action="store_true",
                        help="Tune the final encoder block and head using hard-negative pairs.")
    args = parser.parse_args()
    torch.manual_seed(42)
    torch.set_num_threads(3)
    model = models()[1]
    tokenizer = model.tokenizer
    net = model.model
    train = list(cases("questions.psv", sorted((ROOT / "data").glob("*.pdf"))))
    test = list(cases("gdpr-holdout.psv", [ROOT / "01-EU-GDPR-Regulation-2016-679.pdf",
                                            ROOT / "03-EDPB-Breach-Notification.pdf"]))

    def score():
        net.eval()
        recalls = {1: [], 5: [], 10: []}
        with torch.no_grad():
            for q, passages, gold in test:
                order = net(**inputs(tokenizer, q, passages)).logits.flatten().argsort(descending=True)
                ranked = [passages[i] for i in order.tolist()]
                for k in recalls:
                    recalls[k].append(len(covered(gold, ranked[:k])) / len(gold))
        return {f"recall@{k}": mean(values) for k, values in recalls.items()}

    baseline = score()
    for p in net.parameters():
        p.requires_grad_(False)
    for p in net.classifier.parameters():
        p.requires_grad_(True)
    if args.pairwise:
        for p in net.base_model.encoder.layer[-1].parameters():
            p.requires_grad_(True)
    optimizer = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],
                                  lr=2e-5 if args.pairwise else .0007)
    net.eval()
    pairs = 0
    training_batches = []
    for q, passages, gold in train:
        positive = [p for p in passages if covered(gold, [p])]
        negative = [p for p in passages if not covered(gold, [p])]
        if not positive or not negative:
            continue
        if args.pairwise:
            with torch.no_grad():
                order = net(**inputs(tokenizer, q, negative)).logits.flatten().argsort(descending=True)
            negative = [negative[i] for i in order[:5].tolist()]
        else:
            negative = negative[:5]
        training_batches.append((inputs(tokenizer, q, positive + negative), len(positive), len(negative)))
    for _ in range(3):
        for batch, positives, negatives in training_batches:
            optimizer.zero_grad()
            logits = net(**batch).logits.flatten()
            if args.pairwise:
                margins = logits[:positives, None] - logits[None, positives:]
                loss = torch.nn.functional.softplus(-margins).mean()
                pairs += positives * negatives
            else:
                labels = torch.tensor([1.] * positives + [0.] * negatives)
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
                pairs += positives + negatives
            loss.backward()
            optimizer.step()
    result = {"train": "copyright", "test": "GDPR", "training_pairs_across_epochs": pairs,
              "epochs": 3, "candidate_count": 20, "pretrained": baseline,
              "fine_tuned_pairwise" if args.pairwise else "fine_tuned_head": score()}
    output = ROOT / "evaluation-results" / "reranker-evaluation"
    output.mkdir(parents=True, exist_ok=True)
    filename = "pairwise.json" if args.pairwise else "metrics.json"
    (output / filename).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
