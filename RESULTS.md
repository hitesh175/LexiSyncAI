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
