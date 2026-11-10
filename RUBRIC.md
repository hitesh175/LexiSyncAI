# Assignment coverage

This checklist distinguishes application functionality from the evidence required for marks. It makes no grade prediction.

| Rubric component | Coverage and verification |
|---|---|
| Live demo, 15 marks | A timed script and slides cover upload, factual evidence, multi-page evidence and abstention. A separate single-PDF pipeline rehearsal passed with a two-page citation and an abstention. The actual exam document and timed live delivery still need to be demonstrated. |
| Functional UI, 10 marks | Upload 1–5 public PDFs, save cases, inspect detected structure, ask questions, browse saved answers, view confidence and exact citations, inspect original pages, and export text. The one-PDF option supports the unseen-document exam. |
| Technical depth, 30 marks | Clause-aware ingestion, two-column heuristic, scan flags, BM25, dense retrieval, rank fusion, cross-encoder reranking, local Ollama generation, evidence verification and abstention. The copyright regression set and fresh 15-question GDPR evaluation each include three multi-page and three unanswerable questions. Read RESULTS.md for measured quality and failure cases. |
| Extended features, 15 marks | See the feature-by-feature inventory below. Partial features still need their rubric-specific measurements. |
| Code and documentation, 10 marks | Pinned direct dependencies and model revisions, Git history, tests, Windows launcher, Docker Compose setup, setup guide and one-page architecture diagram. The README links to the GitHub Actions run history for container verification. |
| Attendance and assignments, 20 marks | Assessed separately by the professor. |
| Submission | Documentation, slides and local source history are ready to review. The GitHub URL and eCampus submission are pending. |

## Extended features

| Feature | Status |
|---|---|
| OCR | Optional Windows OCR is implemented. Three rasterized public legal pages yielded 1.00% aggregate word error, and unavailable-engine fallback is tested. Degraded and handwritten pages have not been evaluated. |
| Table extraction | Ruled tables preserve spanning column headers and merged row labels. All 18 manually labeled cells across three tables in the EDPB annex matched their values and row and column labels. Borderless, scanned, and cross-page tables remain open. |
| Chart or figure reading | A local vision model inspects one selected PDF page and shows the original for review. A synthetic raster chart yielded 2/2 correct figure-only answers and 0/4 unsupported answers on missing-evidence checks. Performance on real legal figures remains unmeasured. |
| Bounding-box citations | A uniquely located quote is marked on the rendered page. Rotated pages, absent matches and repeated matches show the full page. The regression test checks one successful and one missing region. A 10-quote sample found 9 correct highlights, 0 incorrect regions and 1 ambiguous full-page fallback. See RESULTS.md for the reference method and sample limitations. |
| Planner and verifier | A verifier rejection with a reason triggers one repair and a second check. Saved analysis details display the outcome. The repair and step cap are tested. The trace also records the rejection reason. |
| Fine-tuned retrieval | The scoring-head experiment and the hard-negative pairwise experiment both tied the pretrained model at Recall@1, @5 and @10. The optional feature's measured-gain criterion remains open. |
| Extended ablation | All six text, text + tables, and text + tables + figure conditions ran on four shared questions with and without model review. Structured table evidence helped. The figure observation omitted the relation needed to answer. See RESULTS.md for scores and traces. |
| Autoencoder | A reproducible page anomaly experiment detected 10/10 blank and 10/10 occluded pages, flagged 0/10 clean pages, and missed 10/10 rotated pages. The detector is an offline experiment on one PDF. |
| Cross-document evidence | The historical copyright comparison now cites both editions and the subsection-specific amendment note that explains the different wording. Tests cover missing sources, missing notes, notes from another section, and changes beyond the documented substitution. Broader conflicts still use the existing evidence verification flow. |
| Public deployment | Open. The tested app is local. |
| Latency and cost | Benchmark latency, per-answer timings and Ollama token counts are available. The single-PDF rehearsal reports first and repeat question timing, and the URL import latency check compares one verifier optimization. A six-run warm comparison measured a small token reduction with no latency improvement. A broader study is open. |

## Known limitations

Column and heading detection are heuristic. Scanned pages with OCR disabled or unsuccessful are excluded from text retrieval. A genuine quote can still be interpreted incorrectly, and a refusal can reflect missed evidence. The confidence label describes the verifier's judgment rather than a calibrated probability.
