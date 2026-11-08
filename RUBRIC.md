# Assignment coverage

This checklist distinguishes application functionality from the evidence required for marks. It makes no grade prediction.

| Rubric component | Coverage and verification |
|---|---|
| Live demo, 15 marks | A timed script and slides cover upload, factual evidence, multi-page evidence and abstention. A separate single-PDF pipeline rehearsal passed with a two-page citation and an abstention. The actual exam document and timed live delivery still need to be demonstrated. |
| Functional UI, 10 marks | Upload 1–5 public PDFs, save cases, inspect detected structure, ask questions, browse saved answers, view confidence and exact citations, inspect original pages, and export text. The one-PDF option supports the unseen-document exam. |
| Technical depth, 30 marks | Clause-aware ingestion, two-column heuristic, scan flags, BM25, dense retrieval, rank fusion, cross-encoder reranking, local Ollama generation, evidence verification and abstention. The copyright regression set and fresh 15-question GDPR evaluation each include three multi-page and three unanswerable questions. Read RESULTS.md for measured quality and failure cases. |
| Extended features, 15 marks | See the feature-by-feature inventory below. Partial features still need their rubric-specific measurements. |
| Code and documentation, 10 marks | Pinned direct dependencies and model revisions, local Git history, tests, Windows launcher, Docker configuration, setup guide and one-page architecture diagram. Docker is provided as a configuration and has not been exercised here. |
| Attendance and assignments, 20 marks | Assessed separately by the professor. |
| Submission | Documentation, slides and local source history are ready to review. The GitHub URL and eCampus submission are pending. |

## Extended features

| Feature | Status |
|---|---|
| OCR | Image-only detection is available. OCR and measured accuracy are open. |
| Table extraction | Basic ruled-table extraction. Merged-cell validation and table accuracy are open. |
| Chart or figure reading | Open. |
| Bounding-box citations | A uniquely located quote is marked on the rendered page. Rotated pages, absent matches and repeated matches show the full page. The regression test checks one successful and one missing region. A 10-quote sample found 9 correct highlights, 0 incorrect regions and 1 ambiguous full-page fallback. See RESULTS.md for the reference method and sample limitations. |
| Planner and verifier | A verifier rejection with a reason triggers one repair and a second check. Saved analysis details display the outcome. The repair and step cap are tested. The trace also records the rejection reason. |
| Fine-tuned retrieval | Open. The retrieval models use pretrained weights. |
| Extended ablation | Dense versus hybrid and retrieval configuration comparisons are measured. Text versus table versus figure ablation is open. |
| Cross-document evidence | The fixture tests two-document synthesis. Prompts ask for conflicting evidence to be cited on both sides. The two-document historical conflict test abstained after repair. Reliable conflict reconciliation is open. |
| Public deployment | Open. The tested app is local. |
| Latency and cost | Benchmark latency, per-answer timings and Ollama token counts are available. The single-PDF rehearsal reports first and repeat question timing, and the URL import latency check compares one verifier optimization. A six-run warm comparison measured a small token reduction with no latency improvement. A broader study is open. |

## Known limitations

Column and heading detection are heuristic. Scanned text is excluded. A genuine quote can still be interpreted incorrectly, and a refusal can reflect missed evidence. The confidence label describes the verifier's judgment rather than a calibrated probability.
