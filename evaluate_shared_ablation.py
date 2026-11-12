"""Compare cumulative evidence modes on a shared four-question fixture."""
from dataclasses import asdict
from functools import partial
import json
from pathlib import Path
import re
from time import perf_counter

from evaluate_figures import chart_page
from figures import read_figure
from lexic import Passage, VERIFY, answer, ask_model, ingest


ROOT = Path(__file__).resolve().parent
QUESTIONS = (
    ("text", "How many examples illustrate the application of the methodology at the end of the EDPB annex?",
     (r"\b(?:two|2)\b",)),
    ("table", "What is the static starting-amount range for an Article 83(4) infringement of high seriousness?",
     (r"\b2(?:[,. ]?000[,. ]?000|\s*(?:to|million|m\b)|\s*[–-])",
      r"\b10(?:[,. ]?000[,. ]?000|\s*(?:million|m\b))")),
    ("figure", "What color is the tallest bar in the chart?", (r"\bgreen\b",)),
    ("unanswerable", "What is the name of the person who created the chart?", ()),
)


def without_verifier(prompt, payload, usage):
    if prompt == VERIFY:
        return {"verdict": "high"}
    return ask_model(prompt, payload, usage=usage)


def main():
    pdf = ROOT / "02-EDPB-Administrative-Fines.pdf"
    passages, _ = ingest({pdf.name: pdf.read_bytes()})
    text = [p for p in passages if p.page == 44 and not p.section.startswith("Detected table")]
    tables = [p for p in passages if p.page == 44 and p.section.startswith("Detected table")]
    assert text and tables
    started = perf_counter()
    description = read_figure(chart_page(), "List the three bars in this chart by color and relative height.")
    vision_seconds = perf_counter() - started
    visual = Passage("synthetic-chart.pdf", 1, "Vision model observation", description)
    modes = {"text": text, "text + tables": tables + text,
             "text + tables + figures": [visual] + tables + text}
    runs = []
    for mode, evidence in modes.items():
        for verify in (False, True):
            for kind, question, patterns in QUESTIONS:
                usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
                started = perf_counter()
                result = answer(question, evidence,
                                partial(ask_model if verify else without_verifier, usage=usage))
                claims = result["claims"]
                joined = " ".join(claim["text"] for claim in claims)
                match = all(re.search(p, joined, re.I) for p in patterns) if patterns else not claims
                runs.append(dict(mode=mode, verifier=verify, kind=kind, question=question,
                                 matches_reference=match, seconds=perf_counter() - started,
                                 usage=usage, result=result))
                print(mode, verify, kind, match, flush=True)
    output = ROOT / "evaluation-results" / "ablation-evaluation" / "shared.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "vision_seconds": vision_seconds,
        "evidence": {mode: [asdict(p) for p in evidence] for mode, evidence in modes.items()},
        "runs": runs,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
