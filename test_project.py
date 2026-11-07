from contextlib import closing
import csv
from pathlib import Path
import unittest

import pypdfium2 as pdfium
from lexic import Passage, answer, ingest
from preview import render_citation

ROOT = Path(__file__).resolve().parent


class ProjectTests(unittest.TestCase):
    def test_benchmark_labels_and_page_render(self):
        docs = {p.name: p.read_bytes() for p in (ROOT / "data").glob("*.pdf")}
        self.assertEqual(len(docs), 2)
        passages, structure = ingest(docs)
        self.assertEqual(len(structure), 9)
        self.assertTrue(all(row["columns"] == 2 for row in structure))
        self.assertFalse(any("TITLE 17—CO" in p.text for p in passages))
        keys = {f"{p.document[7:10]}:{p.page}:{p.section}" for p in passages}
        with (ROOT / "questions.psv").open(encoding="utf-8-sig") as file:
            questions = list(csv.DictReader(file, delimiter="|"))
        self.assertEqual(len(questions), 15)
        for q in questions:
            self.assertTrue(set(filter(None, q["gold"].split(";"))) <= keys, q)
        with closing(pdfium.PdfDocument(docs["17-USC-106.pdf"])) as pdf:
            with closing(pdf[0]) as page, closing(page.render(scale=.5)) as bitmap:
                self.assertGreater(bitmap.width, 0)

    def test_grounded_claim(self):
        passage = Passage("sample.pdf", 1, "Section 7", "The cap is EUR 2 million.")
        claim = {"text": "The cap is EUR 2 million.",
                 "evidence": [{"id": 1, "quote": "EUR 2 million"}]}
        responses = iter([{"claims": [claim]}, {"verdict": "high"}])
        self.assertEqual(answer("What is the cap?", [passage], lambda *_: next(responses))["claims"], [claim])

    def test_fabricated_quote_and_verifier_rejection(self):
        passage = Passage("sample.pdf", 1, "Section 7", "The cap is EUR 2 million.")
        for quote in ("EUR 2 million", "EUR 8 million"):
            claim = {"text": "The cap is EUR 8 million.",
                     "evidence": [{"id": 1, "quote": quote}]}
            responses = iter([{"claims": [claim]}, {"verdict": "reject"}])
            self.assertEqual(answer("What is the cap?", [passage], lambda *_: next(responses))["claims"], [])


    def test_verifier_repairs_once(self):
        passage = Passage("sample.pdf", 1, "Section 7", "The cap is EUR 2 million.")
        claim = {"text": "The cap is EUR 2 million.",
                 "evidence": [{"id": 1, "quote": "EUR 2 million"}]}
        calls = []
        responses = iter([{"claims": [claim]}, {"verdict": "reject", "reason": "Check the cap."},
                          {"claims": [claim]}, {"verdict": "high"}])

        def generate(prompt, payload):
            calls.append(payload)
            return next(responses)

        result = answer("What is the cap?", [passage], generate)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[2]["retry_feedback"], "Check the cap.")
        self.assertEqual(result["claims"], [claim])
        self.assertIn("Accepted the revised draft.", result["trace"])

        calls.clear()
        rejection = {"verdict": "reject", "reason": "Check the cap."}
        responses = iter([{"claims": [claim]}, rejection, {"claims": [claim]}, rejection])
        refused = answer("What is the cap?", [passage], generate)
        self.assertEqual(len(calls), 4)
        self.assertEqual(refused["claims"], [])
        self.assertIn("Abstained after repair.", refused["trace"])

    def test_numbered_factor_cannot_use_another_factors_quote(self):
        wrong = Passage("sample.pdf", 1, "Factors", "(4) The potential market effect.")
        correct = Passage("sample.pdf", 1, "Factors", "(3) The amount used.")
        wrong_claim = {"text": "The third fair use factor is the market effect.",
                       "evidence": [{"id": 1, "quote": wrong.text}]}
        corrected_claim = {"text": "The third fair use factor is the amount used.",
                           "evidence": [{"id": 2, "quote": correct.text}]}
        calls = []
        responses = iter([{"claims": [wrong_claim]}, {"claims": [corrected_claim]}, {"verdict": "high"}])

        def generate(prompt, payload):
            calls.append(payload)
            return next(responses)

        result = answer("What is the third fair use factor?", [wrong, correct], generate)
        self.assertEqual(len(calls), 3)
        self.assertIn("factor 3", calls[1]["retry_feedback"])
        self.assertEqual(result["claims"], [corrected_claim])
        self.assertIn("The cited factor number did not match the draft.", result["trace"])

        notes = Passage("sample.pdf", 2, "Historical notes",
                        "The Committee amended the first of the criteria.")
        wrong_claim["evidence"] = [{"id": 1, "quote": notes.text}]
        result = answer("What is the third fair use factor?", [notes], lambda *_: {"claims": [wrong_claim]})
        self.assertEqual(result["claims"], [])
        self.assertIn("Abstained after repair.", result["trace"])

    def test_citation_highlight_and_missing_quote(self):
        pdf = (ROOT / "data" / "17-USC-106.pdf").read_bytes()
        marked, found = render_citation(pdf, 1, "Exclusive rights in copyrighted works")
        original, missing = render_citation(pdf, 1, "This quote is absent")
        self.assertTrue(found)
        self.assertFalse(missing)
        self.assertEqual(marked.size, original.size)
        self.assertNotEqual(marked.tobytes(), original.tobytes())


if __name__ == "__main__":
    unittest.main()





