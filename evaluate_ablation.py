"""Run a controlled table and verifier ablation on one annotated question."""
import json
from pathlib import Path

from lexic import Index, VERIFY, answer, ask_model, ingest

ROOT = Path(__file__).resolve().parent
QUESTION = ("What static starting-amount range does the EDPB table on PDF page 44 give "
            "for an Article 83(4) infringement of high seriousness, and what dynamic "
            "range does it give for turnover above 500 million?")


def main():
    pdf = ROOT / "02-EDPB-Administrative-Fines.pdf"
    passages, _ = ingest({pdf.name: pdf.read_bytes()})
    results = []
    for tables in (False, True):
        corpus = [p for p in passages if tables or not p.section.startswith("Detected table")]
        hits = Index(corpus).retrieve(QUESTION)
        for verify in (False, True):
            def generate(prompt, payload):
                if not verify and prompt == VERIFY:
                    return {"verdict": "high"}
                return ask_model(prompt, payload)
            result = answer(QUESTION, hits, generate)
            for claim in result["claims"]:
                for citation in claim["evidence"]:
                    passage = hits[citation["id"] - 1]
                    citation.update(page=passage.page, section=passage.section)
            results.append({"structured_table_passages": tables, "model_verifier": verify,
                            "result": result})
            print(tables, verify, result["confidence"], flush=True)
    output = ROOT / "ablation-evaluation"
    output.mkdir(exist_ok=True)
    (output / "table-and-verifier.json").write_text(json.dumps(
        {"question": QUESTION, "runs": results}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
