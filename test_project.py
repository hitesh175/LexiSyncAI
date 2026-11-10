from contextlib import closing
import csv
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image
from cases import CaseStore
from lexic import Index, Passage, answer, answer_standalone_questions, ingest, question_parts
from preview import render_citation
from tables import table_cells
from version_comparison import compare_versions

ROOT = Path(__file__).resolve().parent


class ProjectTests(unittest.TestCase):
    def test_standalone_questions_only_see_their_own_passage(self):
        parts = ["Do glasses count?", "When is a test allowed?"]
        hits = [Passage("law.pdf", 4, "Section 4", "Ordinary glasses are considered."),
                Passage("law.pdf", 5, "Section 5", "The test must be job-related.")]
        drafts = []

        def generate(prompt, payload):
            if "draft" in payload:
                return {"verdict": "high"}
            source = hits[len(drafts)]
            drafts.append(payload)
            return {"claims": [{"text": source.text, "evidence": [{"id": 1, "excerpt": 1}]}]}

        result = answer_standalone_questions(parts, hits, generate)
        self.assertEqual([p["question"] for p in drafts], parts)
        for payload, hit in zip(drafts, hits):
            self.assertEqual(list(payload["passages"]), [1])
            self.assertEqual(payload["passages"][1]["page"], hit.page)
        self.assertEqual([c["evidence"][0]["id"] for c in result["claims"]], [1, 2])

    def test_two_named_articles_can_be_verified_separately(self):
        question = "Under Article 7(3), what happens to consent, and under Article 15(3), what is the fee?"
        consent = Passage("law.pdf", 2, "Article 7 (3)", "3. Consent may be withdrawn.")
        fee = Passage("law.pdf", 4, "Article 15 (3)", "3. A reasonable fee may be charged.")
        responses = iter([
            {"claims": []},
            {"claims": [{"text": "Consent may be withdrawn.", "evidence": [{"id": 1, "excerpt": "1"}]}]},
            {"verdict": "high"},
            {"claims": [{"text": "A reasonable fee may be charged.", "evidence": [{"id": 1, "excerpt": 1}]}]},
            {"verdict": "high"},
        ])
        result = answer(question, [consent, fee], lambda *_: next(responses))
        self.assertEqual([c["evidence"][0]["id"] for c in result["claims"]], [1, 2])
        self.assertEqual(answer(question, [consent], lambda *_: {"claims": []})["claims"], [])
        partial = iter([{"claims": []},
                        {"claims": [{"text": "Consent may be withdrawn.", "evidence": [{"id": 1, "excerpt": 1}]}]},
                        {"verdict": "high"}, {"claims": []}])
        self.assertEqual(answer(question, [consent, fee], lambda *_: next(partial))["claims"], [])

    def test_case_citation_audit_exports_only_selected_case(self):
        with TemporaryDirectory() as folder:
            store = CaseStore(Path(folder) / "cases.sqlite3")
            source = "https://example.org/sample.pdf"
            hit = Passage("sample.pdf", 2, "§7", "The deadline is 30 days.", ocr=True)
            case = store.save_case("First", {hit.document: b"pdf"}, [hit], [], {hit.document: source})
            other = store.save_case("Second", {}, [], [])
            refusal = {"confidence": "INSUFFICIENT EVIDENCE", "claims": []}
            store.save_answer(other, "Exclude this question", [], refusal)
            store.save_answer(case, "What is the deadline?", [hit], {
                "confidence": "HIGH", "claims": [
                    {"text": hit.text, "evidence": [{"id": 1, "quote": hit.text}]}
                ],
            })
            store.save_answer(case, "=1+1", [], refusal)
            exported = store.export_citation_audit(case, store.document_sources(case))
        answered, refused = list(csv.DictReader(StringIO(exported.decode("utf-8-sig"))))
        self.assertEqual(answered["Exact excerpt"], hit.text)
        self.assertEqual(answered["PDF page"], "2")
        self.assertEqual(answered["Section"], "§7")
        self.assertEqual(answered["Official source"], source)
        self.assertEqual(answered["OCR"], "Yes")
        self.assertEqual(refused["Question"], "'=1+1")
        self.assertEqual(refused["Status"], "Abstained")
        self.assertEqual(refused["Document"], "")

    def test_version_comparison_requires_matching_amendment_evidence(self):
        question = "How do the editions differ in section 42(a), and what amendment explains the difference?"
        old = Passage("old.pdf", 4, "§42 (a)", "(a) The deadline is thirty days.")
        new = Passage("new.pdf", 5, "§42 (a)", "(a) The deadline is 60 days.")
        heading = Passage("new.pdf", 5, "§42", "§42. Deadlines")
        note = Passage("new.pdf", 6, "Editorial Notes",
                       "Editorial Notes AMENDMENTS 2000—Subsec. (a). Pub. L. 12–34, §2, substituted “60” for “thirty”.")
        hits, result = compare_versions(question, [old, heading, new, note])
        self.assertEqual(hits, [old, new, note])
        self.assertIn("Pub. L. 12–34 (2000)", result["claims"][1]["text"])
        for claim in result["claims"]:
            for citation in claim["evidence"]:
                self.assertIn(citation["quote"], hits[citation["id"] - 1].text)
        self.assertIsNone(compare_versions(question, [old, heading, new]))
        self.assertIsNone(compare_versions(question, [heading, new, note]))
        other_section = Passage("new.pdf", 6, "§43", "§43. Other deadlines")
        self.assertIsNone(compare_versions(question, [old, heading, new, other_section, note]))
        different_rule = Passage("old.pdf", 4, "§42 (a)", "(a) The deadline is thirty business days.")
        self.assertIsNone(compare_versions(question, [different_rule, heading, new, note]))

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

    def test_invalid_citation_repair_lists_valid_excerpt_ids(self):
        passage = Passage("sample.pdf", 1, "Section 7", "Overview. The cap is EUR 2 million.")
        bad = {"text": "The cap is EUR 2 million.", "evidence": [{"id": 1, "excerpt": 99}]}
        repaired = {"text": bad["text"], "evidence": [{"id": 1, "excerpt": 2}]}
        calls = []
        responses = iter([{"claims": [bad]}, {"claims": [repaired]}, {"verdict": "high"}])

        def generate(prompt, payload):
            calls.append(payload)
            return next(responses)

        result = answer("What is the cap?", [passage], generate)
        self.assertIn("Source 1 has these excerpt IDs: 1, 2.", calls[1]["retry_feedback"])
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

        question = "What consideration appears in the third fair use factor?"
        result = answer(question, [wrong, correct], generate)
        self.assertEqual(len(calls), 3)
        self.assertIn("factor 3", calls[1]["retry_feedback"])
        self.assertEqual(result["claims"], [corrected_claim])
        self.assertIn("The cited factor number did not match the draft.", result["trace"])

        notes = Passage("sample.pdf", 2, "Historical notes",
                        "The Committee amended the first of the criteria.")
        wrong_claim["evidence"] = [{"id": 1, "quote": notes.text}]
        result = answer(question, [notes], lambda *_: {"claims": [wrong_claim]})
        self.assertEqual(result["claims"], [])
        self.assertIn("Abstained after repair.", result["trace"])

    def test_fair_use_factor_requires_its_own_subsection_when_available(self):
        intro = Passage("law.pdf", 1, "§107", "The factors to be considered shall include the following.")
        second = Passage("law.pdf", 1, "§107 (2)", "(2) the nature of the copyrighted work;")
        wrong = {"text": "The second fair use factor is market effect.",
                 "evidence": [{"id": 1, "quote": intro.text}]}
        correct = {"text": "The second fair use factor concerns the nature of the copyrighted work.",
                   "evidence": [{"id": 2, "quote": second.text}]}
        responses = iter([{"claims": [wrong]}, {"claims": [correct]}, {"verdict": "high"}])
        payloads = []

        def generate(prompt, payload):
            payloads.append(payload)
            return next(responses)

        question = "What consideration appears in the second fair use factor?"
        result = answer(question, [intro, second], generate)
        self.assertEqual(result["claims"], [correct])
        self.assertIn("The draft did not cite the requested fair use factor.", result["trace"])
        self.assertEqual(list(payloads[1]["passages"]), [2])
        self.assertEqual(list(payloads[2]["sources"]), [2])
        self.assertEqual(answer(question, [intro, second],
                                lambda *_: {"claims": [wrong]})["claims"], [])

    def test_direct_factor_lookup_quotes_the_subsection_or_abstains(self):
        question = "What does the second fair use factor consider?"
        second = Passage("law.pdf", 1, "§107 (2)", "(2) the nature of the copyrighted work;")
        fourth = Passage("law.pdf", 1, "§107 (4)", "(4) the effect on the potential market.")

        def generate(*_):
            self.fail("A direct lookup should not call the model")

        result = answer(question, [fourth, second], generate)
        self.assertEqual(result["claims"][0]["evidence"], [{"id": 2, "quote": second.text}])
        self.assertEqual(answer(question, [fourth], generate)["claims"], [])

    def test_claim_attributed_to_an_article_cites_that_article(self):
        rule = Passage("law.pdf", 1, "Article 8 (2)", "2. The controller must respond within one month.")
        notes = Passage("notes.pdf", 2, "Guidance", "The controller must respond to requests.")
        claim = {"text": "Article 8(2) requires a response within one month.",
                 "evidence": [{"id": 2, "quote": notes.text}]}
        repaired = {**claim, "evidence": [{"id": 1, "quote": rule.text}]}
        calls = iter([{"claims": [claim]}, {"claims": [repaired]}, {"verdict": "high"}])
        result = answer("What deadline does Article 8(2) set?", [rule, notes], lambda *_: next(calls))
        self.assertEqual(result["claims"], [repaired])
        self.assertIn("The claim cited commentary instead of the named article.", result["trace"])

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
        self.assertEqual(question_parts("What is the limit and when does it apply?"),
                         ["What is the limit?", "when does it apply?"])
        self.assertEqual(question_parts("Do glasses count? When is a test allowed?"),
                         ["Do glasses count?", "When is a test allowed?"])

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

    def test_merged_table_headers_and_row_labels(self):
        with pdfplumber.open(ROOT / "02-EDPB-Administrative-Fines.pdf") as pdf:
            top = table_cells(pdf.pages[43].find_tables()[0])
            continuation = table_cells(pdf.pages[44].find_tables()[0])
        cell = next(c for c in top if c.row == 3 and c.columns == (5,))
        self.assertEqual(cell.row_label, "83(4) GDPR")
        self.assertEqual(cell.column_label,
                         "Medium level of seriousness / Dynamic range in the case of a turnover > 500 m")
        self.assertEqual(cell.value, "0.2% - 0.4% of the annual turnover")
        merged = next(c for c in continuation if c.row == 2)
        detail = next(c for c in continuation if c.row == 3 and c.columns == (4,))
        self.assertEqual(merged.columns, (2, 3, 4))
        self.assertEqual(detail.row_label, merged.row_label)
        self.assertEqual(detail.value, "300,000 – 5m")

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
