# Benchmark results

The fixed corpus contains nine PDF pages across two 2023 U.S. Code extracts. The test set contains 12 answerable questions, including three requiring evidence from both documents, and three unanswerable questions.

## Retrieval-only run

| Configuration | Recall@1 | Recall@5 | Recall@10 | All gold at 10 | Mean retrieval time |
|---|---:|---:|---:|---:|---:|
| BM25 | 12.5% | 45.8% | 54.2% | 50.0% | 7 ms |
| Dense MiniLM | 41.7% | 62.5% | 62.5% | 50.0% | 6 ms |
| Reciprocal rank fusion | 29.2% | 54.2% | 62.5% | 58.3% | 7 ms |
| Hybrid with cross-encoder | 41.7% | 50.0% | 70.8% | 66.7% | 558 ms |

Reranked hybrid recovered all required clauses for 8 of 12 answerable questions at ten passages, compared with 6 of 12 for dense retrieval. Dense performed better at five passages. Hybrid added about 552 ms per query on this CPU run. Index startup took about 98 s, including first-time model loading and downloads. See `retrieval-metrics.json` for the raw aggregate.

## Local generation smoke check

Using passages extracted from the §107 PDF, the local Ollama model answered the fourth-factor question with a matching statutory quote and abstained when asked about the absent Acme–Northwind contract. These two checks exercised generation and verification with a supplied passage set. See the full evaluation command in the README for per-question outputs and manual review sheets.

## End-to-end run with local Ollama

| Metric | Dense | Reranked hybrid |
|---|---:|---:|
| Correct answers, including correct abstentions | 6/15 (40.0%) | 4/15 (26.7%) |
| Citation precision | 21/36 (58.3%) | 12/26 (46.2%) |
| Correct abstentions on unanswerable questions | 3/3 | 3/3 |
| False abstentions on answerable questions | 5/12 | 7/12 |
| Mean end-to-end latency | 7.33 s | 9.27 s |

The project author reviewed each output against the reference and its cited quotes. A response needed to answer every part without material factual errors. An individual citation counted if it supported the attached claim or a necessary premise. The denominator includes every emitted citation. Abstentions contain zero citations. The graded CSVs preserve the outputs and scores.

Hybrid retrieved more gold evidence at ten passages, but its generator and verifier still made errors. For example, one draft labeled the potential-market factor as the third factor even though its quote began with “(4),” and the verifier accepted it. That failure separates evidence availability and quote authenticity from correct interpretation. Both configurations missed answerable questions, so the confidence labels require human review.

The run used Windows, the pinned Python dependencies, CPU retrieval with four OpenMP threads, and the default local Qwen model. Index startup with cached model weights took 32.83 seconds. This is a single run on a small fixture.

## Verifier repair rerun, November 7, 2026

The original manually graded results above describe the baseline. The updated app reran all 15 questions with the same fixture. Per-question outputs and review sheets are in `verifier-rerun/`.

| Metric | Dense | Reranked hybrid |
|---|---:|---:|
| Clause recall at 10 | 62.5% | 70.8% |
| Correct abstentions on unanswerable questions | 3/3 | 3/3 |
| False abstentions on answerable questions | 5/12 | 4/12 |
| Mean end-to-end latency | 11.81 s | 10.64 s |

The hybrid repair trace shows that the first draft for the missing royalty-rate question was rejected, repaired once, and then withheld. The rerun still produced numbered-factor errors. Fewer false abstentions do not establish higher correctness. The manual review below scores this rerun separately from the baseline.


### Manual review of the rerun

| Metric | Dense | Reranked hybrid |
|---|---:|---:|
| Correct answers, including correct abstentions | 7/15 (46.7%) | 8/15 (53.3%) |
| Citation precision | 20/26 (76.9%) | 21/29 (72.4%) |

A correct answer resolves the requested question without material factual errors. Citation precision counts a quote only when it supports the attached claim or one of its necessary premises. A correct answer can still contain a weak citation. This is a single manual review of the recorded outputs. The graded CSVs are in `verifier-rerun/`.

Hybrid questions 5 and 6 both used factor (4) as evidence for a different numbered fair-use factor. These examples were selected for a deterministic validation check. The scores above precede that check.

### Numbered-factor guard

A follow-up run on questions 5 and 6 showed why the guard needs to recognize two forms of reference. For question 5 it rejected the mismatched numbered quotation and abstained after one repair. For question 6 it rejected the original draft, but the model then cited a historical note describing the first factor in words and mislabeled it as the third. The guard now checks both leading numbers and phrases such as “first of the criteria” in fair-use citations. Regression tests cover successful repair and withholding a repeated mismatch. The full 15-question scores above have not been rerun with this final guard.

## URL import release latency check

In a warm local comparison on one question with the same supplied passages, the draft and verification steps took 1.33 s before the change and 1.16 s after it. Input tokens decreased from 1,202 to 1,025, with two model calls, 69 output tokens and a HIGH result in each run. This measures only one answer with a warm model and excludes retrieval, index construction and downloads.

## Current build benchmark

The same 15-question fixture was rerun after the numbered-factor check and the smaller verifier request. Raw runs and manually scored review sheets are in `current-benchmark/`.

| Metric | Dense | Reranked hybrid |
|---|---:|---:|
| Clause recall at 10 | 62.5% | 70.8% |
| Correct answers, including correct abstentions | 10/15 (66.7%) | 8/15 (53.3%) |
| Citation precision | 26/28 (92.9%) | 15/21 (71.4%) |
| Correct abstentions on unanswerable questions | 3/3 | 3/3 |
| False abstentions on answerable questions | 5/12 | 6/12 |
| Mean question latency after the index was ready | 5.51 s | 6.03 s |

Index and model preparation took 6.89 s in this run, separately from per-question latency. The runs used the same questions, but first-use loading and machine conditions were not controlled across dates. Do not attribute the timing difference entirely to the code changes. The small fixture does not establish performance on the GDPR pack. Hybrid rejected the numbered mismatch on question 6 and abstained after the repair. It still missed answerable questions, and dense produced more correct answers in this run.

## Held-out GDPR evaluation

The 15-question fixture in `gdpr-holdout.psv` was written and labeled before running the model. It uses the regulation and EDPB breach guidance from the EU GDPR Source Pack, with nine factual questions, three multi-page questions, and three unanswerable questions. The documents were already available during earlier app work. The questions and gold evidence were held out from the previous copyright benchmark and the earlier GDPR fines rehearsal.

| Metric | BM25 | Dense | Fusion | Reranked hybrid |
|---|---:|---:|---:|---:|
| Recall at 1 | 41.7% | 25.0% | 45.8% | 87.5% |
| Recall at 5 | 70.8% | 58.3% | 75.0% | 95.8% |
| Recall at 10 | 79.2% | 62.5% | 95.8% | 100.0% |
| All annotated evidence in top 10 | 9/12 | 6/12 | 11/12 | 12/12 |
| Correct answers, including abstentions | — | 9/15 | — | 13/15 |
| Citation precision | — | 16/25 (64.0%) | — | 26/30 (86.7%) |
| Correct abstentions | — | 3/3 | — | 3/3 |
| False abstentions on answerable questions | — | 3/12 | — | 0/12 |
| Mean question time after index preparation | — | 6.97 s | — | 8.23 s |

Gold locations use exact article paragraphs for the regulation and PDF pages for the two EDPB evidence targets. The page-level targets can match a nearby passage on that page. An answer earns correctness credit for factually resolving the question, and a citation earns separate credit for supporting the attached claim or a necessary premise. Redundant or weak evidence can lower citation precision even if the answer text is right. The manual scoring reflects one reviewer.

Hybrid correctly answered the three multi-page questions in substance. In question 10 it cited a timing discussion instead of the passage that establishes the awareness threshold. In question 7 it converted alternatives into a joint requirement. After scoring, a narrow conjunction check was added for the latter pattern, and exact-clause retrieval was extended to named Section references. The table is the frozen run before these two follow-up fixes. It is not a performance estimate for other legal domains. Raw output and scored sheets are in `heldout-evaluation/`.

### Reproduce

The two PDFs are included in the repository root. Run from the LexiSyncAI directory using your Python environment and a running Ollama service:

```powershell
python evaluate.py --questions gdpr-holdout.psv --docs 01-EU-GDPR-Regulation-2016-679.pdf 03-EDPB-Breach-Notification.pdf --output evaluation-results/gdpr-holdout
```

The source PDFs are [the regulation on EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng/pdf) and [the EDPB breach guidelines](https://www.edpb.europa.eu/system/files/documents/2023-04/edpb_guidelines_202209_personal_data_breach_notification_v2.0_en.pdf).


## Multipart evidence and citation region evaluation

The GDPR fixture was rerun after explicit two-part questions began retrieving evidence separately for each part. These are regression results on the previously graded fixture.

| Metric | Dense rerun | Hybrid rerun |
|---|---:|---:|
| Recall at 1 / 5 / 10 | 25.0% / 58.3% / 62.5% | 87.5% / 100% / 100% |
| Correct answers, including correct abstentions | 9/15 | 12/15 |
| Citation precision | 16/26 (61.5%) | 22/25 (88.0%) |
| Correct abstentions | 3/3 | 3/3 |
| False abstentions on answerable questions | 2/12 | 2/12 |
| Mean question time after preparation | 5.27 s | 5.46 s |

Hybrid citation precision changed from 26/30 (86.7%) to 22/25 (88.0%). Overall correctness declined from 13/15 to 12/15. The breach-awareness answer now cites the statutory deadline on PDF page 52 and the EDPB definition on PDF page 11. The answer also contains a weaker extra claim. The verifier refused two answerable questions after repair. One draft selected an invalid excerpt ID and another combined alternative legal conditions. This was a repeated fixture under uncontrolled machine conditions, so compare accuracy directly and treat the timings as descriptive.

### Citation region sample

Ten deliberately selected quotes span five PDFs, including two-column statutes, line wraps, and a phrase that appears twice. PDFplumber supplied independent text coordinates, and the rendered crops were visually checked. A highlight passed when there was one reference match and at least 50% overlap in both directions. The app produced **9 correct highlights, 0 incorrect highlights, and 1 full-page fallback**. Region precision among rendered highlights was **9/9** and highlight coverage was **9/10**. This sample is small and uses tool-generated reference regions checked by visual review. It is not a manually drawn or statistically representative test set.

Run `python evaluate_regions.py --output region-results` to reproduce the CSV and review image. See [region scores](multipart-evaluation/regions.csv) and [rendered review](multipart-evaluation/region-review.png).

### Layout spot check

| Sample | Observed result |
|---|---|
| GovInfo §106, PDF page 1 | Two-column mode detected. Clauses (1), (2), and (3) remained in order and the running title was removed. |
| EU GDPR, PDF pages 82–83 | Official Journal running headers were excluded from the extracted passages. |
| EDPB breach guidance, PDF page 11 | The awareness passage was searchable. A footnote marker remained attached to a word, and footer material remained in a nearby passage. Clean footnote separation is still open. |
| Image-only copy of the GovInfo page | Detected as image-only, with zero searchable passages. The test rasterized a real page and did not measure OCR. |

### Controlled verifier timing

Three interleaved warm runs per condition used the same question, retrieved passages, model, and verifier prompt. The only difference was whether the verifier also received the full cited passages. Median prompt tokens fell from **1,942 to 1,926**. Median answer-and-check time changed from **2.96 s to 3.17 s**. All six returned a cited answer. This small sample shows a token reduction with no demonstrated latency improvement. Indexing and retrieval were excluded. See [raw timings](multipart-evaluation/controlled-latency.json).

### Repair traces and conflict handling

- **Accepted repair.** A controlled fault injection supplied a nonexistent excerpt number for a synthetic deadline question. The real local model selected the existing excerpt on its one permitted repair, and the verifier accepted it. [Recorded trace](multipart-evaluation/fault-injected-repair.json)
- **Rejected repair.** In the actual GDPR rerun, question 7 combined alternative conditions into a single requirement. The guard recorded the reason and the app abstained after one repair. [Hybrid run](multipart-evaluation/hybrid.json)
- **Version conflict, original pipeline.** The 65-page case combined the original 1976 Act and the 2023 Code. The original pipeline abstained after repair. The draft cited the 1976 Act for the later amendment, and the verifier confused the edition date with the amendment or applicability date. [Full pipeline result](multipart-evaluation/conflict-final.json) · [Supplied-evidence result](multipart-evaluation/conflict-supplied-evidence.json)
- **Version conflict, amendment match.** The app now cites both versions of §302(a) and the 2023 Code's editorial note. The cited term changes from life plus fifty years to life plus seventy years, and the note identifies Pub. L. 105–298 (1998). The check requires the same subsection in two documents and a scoped amendment note that accounts for the only wording change after normalizing whitespace, case and apostrophes. It makes no model calls. Missing, unrelated or ambiguous evidence falls through to the existing answer flow. This run verifies the historical example and does not establish broader conflict resolution. [App result](multipart-evaluation/version-comparison.json) · [1976 Act](https://www.govinfo.gov/content/pkg/STATUTE-90/pdf/STATUTE-90-Pg2541.pdf) · [2023 Code](https://www.govinfo.gov/content/pkg/USCODE-2023-title17/pdf/USCODE-2023-title17-chap3-sec302.pdf)

The regression table above predates the historical margin-label and multiple-edition exact-match refinements. The conflict checks document the version they exercised.

## Extended feature experiments

| Experiment | Measured result | Scope |
|---|---|---|
| Structured table passages and verifier | The static range was incorrectly reported as €800,000–€10 million with structured passages disabled. With them enabled, both the €2–€10 million static range and the 0.4%–2% dynamic range were correct. Turning the model verifier on or off did not change the result. | One EDPB fines question on PDF page 44, four conditions. The ordinary text passages still contained flattened table text. [Answer traces](ablation-evaluation/table-and-verifier.json) |
| Figure-only evidence | With the chart visible, Qwen2.5-VL 3B answered both answerable questions correctly. It abstained on all three blank-control questions and the one chart question whose answer was absent. Observed hallucinations on missing-evidence prompts **0/4**. | One synthetic chart saved as a raster PDF. The figure reader runs separately from the text verifier. [Raw outputs](ablation-evaluation/figure.json) |
| Fine-tuned reranker head | Pretrained and fine-tuned Recall@1/@5/@10 were both **45.8% / 58.3% / 75.0%**. | MiniLM backbone frozen. Trained its classifier head on copyright candidates for three epochs, with 168 pair presentations across epochs. Both versions used the same candidate pools on the GDPR holdout. The app uses the pretrained weights. [Metrics](reranker-evaluation/metrics.json) |
| Autoencoder | Flagged **0/10 clean, 0/10 rotated, 10/10 blank and 10/10 occluded** pages. | 24 GDPR pages for training, eight for calibrating the threshold and ten held-out pages from the same PDF. Anomalies were synthetic. [Metrics](anomaly-evaluation/metrics.json) · [Per-page scores](anomaly-evaluation/page-scores.csv) |
| Historical conflict retest | A verifier prompt change still caused abstention after repair. | A single 65-page case with two editions. The unsuccessful prompt change was left out of the app. [Retest trace](multipart-evaluation/conflict-prompt-retest.json) |

Run these from the project folder with the application's Python environment. The table and figure checks use local Ollama models. The reranker script loads the same pretrained retrieval models as the app.

```powershell
python evaluate_ablation.py
python evaluate_figures.py
python evaluate_anomalies.py
python evaluate_reranker.py
python evaluate_reranker.py --pairwise
```

The pairwise run trains the final MiniLM encoder block and classifier head for three epochs. For each copyright question it pairs passages that match the reference with up to five highly ranked candidates that do not match it. The loss rewards a higher score for the matching passage. The comparison reuses the previous GDPR evaluation set and identical candidate pools for both models. It is a follow-up experiment, so any improvement on this set would need confirmation on a fresh set before changing the app.

After 165 pair presentations, Recall@1/@5/@10 remained **45.8% / 58.3% / 75.0%**, equal to the pretrained baseline. The candidate pools and gold locations remained fixed. The app retains the pretrained reranker. [Pairwise metrics](reranker-evaluation/pairwise.json)

### Shared text, table and figure ablation

Run `python evaluate_shared_ablation.py` with the local text and vision models running. All six conditions use the same four questions. They cover an EDPB prose fact, an EDPB table range, a fact visible only in the synthetic chart, and a question about the chart that cannot be answered. The passages come from a fixed PDF page, which isolates evidence availability from retrieval ranking. Ordinary text can include flattened table cells. The figure condition adds one vision-model observation generated from the chart before the four questions are asked.

All conditions retain the app's exact-excerpt checks. The verifier toggle controls the additional model review and its retry. The text verifier checks the vision model's observation as text. It does not independently inspect the image. This is a controlled evaluation separate from the app's figure reader.

| Evidence supplied | Correct without model review | Correct with model review |
|---|---:|---:|
| Text | 2/4 | 2/4 |
| Text + structured tables | 3/4 | 2/4 |
| Text + structured tables + figure observation | 2/4 | 2/4 |

The score counts correct requested facts and correct abstentions. It does not count citation quality separately. The best condition on this sample answered the prose and table questions and abstained on the question with no answer. With model review enabled, a draft cited a table for the prose fact and abstained after the verifier rejected the citation. The chart observation listed the bar colors and omitted relative height. Both drafts that received it incorrectly identified orange as the tallest bar, including the draft accepted by the verifier. The direct figure reader answered that question correctly in the earlier experiment. [All 24 runs and supplied evidence](ablation-evaluation/shared.json)

### Targeted answer reliability regression

This check compares the uploaded baseline (`cd17341`) and the updated hybrid answer flow on eight previously reviewed questions: GDPR IDs 3, 6, 7 and 13, and copyright IDs 5, 6, 10 and 13. It covers two document bundles with one unanswerable control per bundle. The questions were selected because the earlier reviews exposed failures, so the results describe this regression sample rather than performance on new PDFs. [Paired answers and citations](reliability-evaluation/targeted.json)

The updated path recognizes follow-up clauses after “and” even without a comma, identifies valid excerpt numbers during the single repair, and checks that answers about numbered fair-use factors cite the requested factor when available. When a claim explicitly attributes a rule to a named GDPR-style article and its exact subsection was retrieved, the app requires that source in the citations.

| Observation | Baseline | Updated |
|---|---:|---:|
| Complete labeled evidence in retrieved passages, answerable questions | 3/6 | 5/6 |
| False abstentions on answerable questions | 4/6 | 1/6 |
| Correct abstentions on unanswerable controls | 2/2 | 2/2 |

Manual review found that the updated answers recovered the GDPR response and extension deadlines, the direct-notification threshold and timing, the missing record-keeping risk trigger, and the third copyright fair-use factor. The response-deadline answer gives the one-month outer limit but omits the initial “without undue delay” qualifier in its prose. The second fair-use factor remains a false abstention even though the correct subsection was retrieved. The two-document teaching-use answer still relies on commentary for part of its support. These are targeted reliability measurements, so the earlier full-fixture accuracy and citation precision numbers remain separate.

**Follow-up on the second fair-use factor.** Restricting the model's repair to the requested subsection still produced a refusal for the second factor. A control with that subsection removed produced an incorrect guess. The app now handles narrowly phrased requests for a single named factor as a direct lookup. It requires a uniquely identified, non-OCR subsection with the correct number and returns its text and PDF location. If the subsection is missing or ambiguous, the lookup abstains. Other numbered-factor questions can still use the model's focused repair, with original citation IDs and verification intact.

In the bundled copyright PDFs, all four direct lookups returned the matching statutory factor. The lookup abstained with the second subsection removed from retrieved evidence, and the regular answer flow abstained on the unrelated royalty-rate question. [Six verification cases](reliability-evaluation/focused-retry.json)

## Scanned-page OCR evaluation

With **Read scanned pages (OCR)** enabled, Windows OCR processes image-only pages. Recognized text becomes searchable and remains linked to the original PDF page. A citation derived from OCR is labeled as a transcription in the source pane and exported answer.

| Public source sample | Original PDF page | Word edits / reference words | Word error rate | OCR plus ingestion |
|---|---:|---:|---:|---:|
| EU GDPR regulation | 37 | 9 / 555 | 1.62% | 0.71 s |
| EU GDPR regulation | 52 | 2 / 561 | 0.36% | 0.65 s |
| EDPB breach notification guidance | 11 | 6 / 592 | 1.01% | 0.67 s |
| **Aggregate** | **3 pages** | **17 / 1,708** | **1.00%** | — |

Each page was rasterized from a public PDF to remove its text layer. The original text layer provided the reference. Word error rate is the number of insertions, deletions and substitutions divided by reference words after Unicode normalization, case folding and punctuation removal. These clean generated scans do not measure performance on handwriting, skew, damaged documents, or other languages.

With OCR disabled, all three pages were flagged as image-only and produced no searchable passages. With OCR enabled, all three became searchable. An automated test also checks the unavailable-engine fallback. Failed pages stay flagged, and a case with no searchable text shows a setup message.

Reproduce on Windows with installed OCR language resources using `python evaluate_ocr.py`. See [page-level results](ocr-evaluation/ocr-sample.csv) and [Windows OCR documentation](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine).

In a separate end-to-end check, the app indexed only the rasterized GDPR page 37. For a question about withdrawal of consent, it returned a cited answer using the OCR-derived text on the only PDF page. The displayed confidence was HIGH. This is a single functional check, not a separate answer-accuracy benchmark.

## Merged table evaluation

The table extractor maps each cell's physical rectangle to its row and leaf columns. It carries a vertically merged row label into the detail rows it spans and joins grouped headers with their subheaders. A horizontally merged data cell records the columns it covers. The cited excerpt is a structured transcription of a cell, with its table, row, column, and value. The source viewer opens the original PDF page for inspection.

| Manually annotated source table | Cells | Values correct | Row labels correct | Column labels correct |
|---|---:|---:|---:|---:|
| EDPB fines guidance, PDF page 44, first table | 6 | 6 | 6 | 6 |
| EDPB fines guidance, PDF page 45 | 6 | 6 | 6 | 6 |
| EDPB fines guidance, PDF page 46 | 6 | 6 | 6 | 6 |
| **Total** | **18** | **18** | **18** | **18** |

Expected values and labels were transcribed from the rendered PDF pages. The comparison normalizes whitespace and dash variants while keeping amounts, units and labels intact. The sample includes two-level column headers, horizontally merged values and vertically merged row labels. All three tables are from the same ruled annex, so these results do not establish accuracy on unrelated layouts, borderless tables, or scanned tables. The extractor does not join table continuations across pages.

Run `python evaluate_tables.py` to regenerate [the cell-by-cell results](table-evaluation/results.csv) from the [manual annotations](table-evaluation/gold.psv). The source is the [official EDPB fines guidance](https://www.edpb.europa.eu/system/files/2023-06/edpb_guidelines_042022_calculationofadministrativefines_en.pdf).

In a separate end-to-end check, the model answered a comparison of the static and dynamic starting ranges for the same high-seriousness row. It cited two different columns of row 3 in the first table on PDF page 44. These are illustrative ranges in the guidance, and the test scored cell selection rather than regulatory interpretation. [Recorded answer and source locations](table-evaluation/answer.json)
