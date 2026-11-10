"""Fine-tune the cross-encoder scoring head and compare frozen held-out ranks."""
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
    optimizer = torch.optim.AdamW(net.classifier.parameters(), lr=.0007)
    net.eval()
    pairs = 0
    for _ in range(3):
        for q, passages, gold in train:
            positive = [p for p in passages if covered(gold, [p])]
            negative = [p for p in passages if not covered(gold, [p])][:5]
            if not positive or not negative:
                continue
            labels = torch.tensor([1.] * len(positive) + [0.] * len(negative))
            optimizer.zero_grad()
            logits = net(**inputs(tokenizer, q, positive + negative)).logits.flatten()
            torch.nn.functional.binary_cross_entropy_with_logits(logits, labels).backward()
            optimizer.step()
            pairs += len(labels)
    result = {"train": "copyright", "test": "GDPR", "training_pairs_across_epochs": pairs,
              "epochs": 3, "candidate_count": 20, "pretrained": baseline, "fine_tuned_head": score()}
    output = ROOT / "reranker-evaluation"
    output.mkdir(exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
