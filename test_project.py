from contextlib import closing
import csv
from io import BytesIO
from pathlib import Path
import unittest

import pypdfium2 as pdfium
from PIL import Image
from lexic import Index, Passage, answer, ingest, question_parts
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

    def test_selected_excerpt_is_copied_from_source(self):
        passage = Passage("sample.pdf", 1, "Section 7",
                          "This is an example. The cap is EUR 2 million.")
        claim = {"text": "The cap is EUR 2 million.",
                 "evidence": [{"id": 1, "excerpt": 2}]}

        def generate(prompt, payload):
            if "passages" in payload:
                self.assertEqual(payload["passages"][1]["excerpts"][2], "The cap is EUR 2 million.")
                return {"claims": [claim]}
            self.assertEqual(payload["draft"][0]["evidence"], [{"id": 1, "quote": "The cap is EUR 2 million."}])
            return {"verdict": "high"}

        result = answer("What is the cap?", [passage], generate)
        self.assertEqual(result["claims"][0]["evidence"][0]["quote"], "The cap is EUR 2 million.")

    def test_quote_mismatch_repairs_without_accepting_a_paraphrase(self):
        passage = Passage("sample.pdf", 1, "Section 7", "The cap is EUR 2 million.")
        bad = {"text": "The cap is EUR 2 million.",
               "evidence": [{"id": 1, "quote": "The cap is two million euros."}]}
        good = {**bad, "evidence": [{"id": 1, "quote": "EUR 2 million"}]}
        responses = iter([{"claims": [bad]}, {"claims": [good]}, {"verdict": "high"}])
        result = answer("What is the cap?", [passage], lambda *_: next(responses))
        self.assertEqual(result["claims"], [good])
        self.assertIn("A proposed quote did not match its source text.", result["trace"])
        refused = answer("What is the cap?", [passage], lambda *_: {"claims": [bad]})
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

    def test_repair_does_not_turn_alternative_triggers_into_requirements(self):
        quote = ("The rule does not apply unless the processing is likely to result in a risk, "
                 "the processing is not occasional, or it includes sensitive data.")
        passage = Passage("sample.pdf", 2, "Section 5", quote)
        wrong = {"text": "The rule applies only if processing is not occasional and is likely to result in a risk.",
                 "evidence": [{"id": 1, "quote": quote}]}
        correct = {"text": "The rule applies if processing is likely to result in a risk, is not occasional, or includes sensitive data.",
                   "evidence": [{"id": 1, "quote": quote}]}
        responses = iter([{"claims": [wrong]}, {"claims": [correct]}, {"verdict": "high"}])
        result = answer("When does the rule apply?", [passage], lambda *_: next(responses))
        self.assertEqual(result["claims"], [correct])
        self.assertIn("The draft combined alternatives into one requirement.", result["trace"])

    def test_hybrid_preserves_evidence_for_both_explicit_question_parts(self):
        question = "When is notice due, and what counts as awareness?"
        due, aware = question_parts(question)
        a = Passage("law.pdf", 1, "Notice", "Notify promptly.")
        b = Passage("guidance.pdf", 2, "Awareness", "Awareness requires reasonable certainty.")
        c = Passage("law.pdf", 2, "Procedure", "Keep a record of notices.")
        index = Index.__new__(Index)
        ranks = {due: [a, c], aware: [b, a]}
        index._rank = lambda part, k, mode: ranks[part]
        self.assertEqual(index.retrieve(question, k=3), [a, b, c])
        self.assertEqual(len(question_parts("Compare Articles 5, 6, and 7.")), 1)

    def test_image_only_ocr_and_engine_unavailable_fallback(self):
        output = BytesIO()
        Image.new("RGB", (120, 120), "white").save(output, format="PDF")
        docs = {"scan.pdf": output.getvalue()}

        def unavailable(*args):
            raise ImportError("Optional OCR engine is unavailable")

        passages, structure = ingest(docs, ocr_reader=unavailable)
        self.assertEqual(passages, [])
        self.assertTrue(structure[0]["image_only"])
        self.assertEqual(structure[0]["ocr_status"], "engine unavailable")
        passages, structure = ingest(docs, ocr_reader=lambda *_: "Section 7\nThe deadline is thirty days.")
        self.assertTrue(all(p.ocr for p in passages))
        self.assertIn("The deadline is thirty days.", passages[0].text)
        self.assertEqual(structure[0]["ocr_status"], "recognized")

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
