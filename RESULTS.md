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
