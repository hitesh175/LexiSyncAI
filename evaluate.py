import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from lexic import Index, answer, ingest

ROOT = Path(__file__).resolve().parent
MODES = ("bm25", "dense", "fusion", "hybrid")


def key(p):
    return (p.document.removeprefix("17-USC-").removesuffix(".pdf"), str(p.page), p.section)


def covered(gold, hits):
    locations = {key(p) for p in hits}
    pages = {(document, page, "*") for document, page, _ in locations}
    return gold & (locations | pages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--questions", type=Path, default=ROOT / "questions.psv")
    parser.add_argument("--docs", type=Path, nargs="+", default=sorted((ROOT / "data").glob("*.pdf")))
    parser.add_argument("--output", type=Path, default=Path("evaluation-results"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with args.questions.open(encoding="utf-8-sig") as file:
        questions = list(csv.DictReader(file, delimiter="|"))
    docs = {f.name: f.read_bytes() for f in args.docs}
    passages, _ = ingest(docs)
    for row in questions:
        gold = {tuple(item.split(":", 2)) for item in row["gold"].split(";") if item}
        if gold != covered(gold, passages):
            raise ValueError(f"Question {row['id']} has an evidence label missing from the corpus.")
    started = perf_counter()
    index = Index(passages)
    summary = {"index_seconds": perf_counter() - started}
    for mode in MODES:
        runs, recalls, complete, times, abstentions = [], [], [], [], []
        for row in questions:
            gold = {tuple(item.split(":", 2)) for item in row["gold"].split(";") if item}
            started = perf_counter()
            hits = index.retrieve(row["question"], mode=mode)
            retrieval_seconds = perf_counter() - started
            recalls.append({f"recall@{k}": len(covered(gold, hits[:k])) / len(gold)
                            for k in (1, 5, 10)} if gold else {})
            if gold:
                complete.append(gold == covered(gold, hits))
            run = dict(row, retrieval_seconds=retrieval_seconds, hits=[key(p) for p in hits])
            if not args.retrieval_only and mode in ("dense", "hybrid"):
                result = answer(row["question"], hits)
                run.update(result)
                run["seconds"] = perf_counter() - started
                times.append(run["seconds"])
                if not gold:
                    abstentions.append(not result["claims"])
            runs.append(run)
        metrics = {f"recall@{k}": mean(r[f"recall@{k}"] for r in recalls if r)
                   for k in (1, 5, 10)}
        metrics["all_gold_retrieved@10"] = mean(complete)
        metrics["mean_retrieval_seconds"] = mean(r["retrieval_seconds"] for r in runs)
        if times:
            metrics.update(mean_end_to_end_seconds=mean(times),
                           unanswerable_abstention_accuracy=mean(abstentions),
                           answerable_false_abstention=mean(not r["claims"] for r in runs if r["gold"]))
            with (args.output / f"{mode}-review.csv").open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["id", "question", "reference", "claims_and_quotes", "citation_locations",
                                 "correct_0_or_1", "supported_citations", "total_citations"])
                for r in runs:
                    writer.writerow([r["id"], r["question"], r["reference"],
                                     json.dumps(r["claims"], ensure_ascii=False), json.dumps(r["hits"], ensure_ascii=False),
                                     "", "", sum(len(c["evidence"]) for c in r["claims"])])
        summary[mode] = metrics
        (args.output / f"{mode}.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    report = json.dumps(summary, indent=2)
    (args.output / "metrics.json").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

