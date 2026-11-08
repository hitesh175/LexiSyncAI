# Single-PDF rehearsal

Use [17 U.S.C. Chapter 2, 2023 edition](https://www.govinfo.gov/content/pkg/USCODE-2023-title17/pdf/USCODE-2023-title17-chap2.pdf). The eight-page PDF in this folder was outside the earlier copyright and GDPR evaluation cases.

## Five-minute sequence

1. **0:00–0:45** Show the architecture. Explain extraction, hybrid retrieval, and the evidence check.
2. **0:45–1:30** Upload the PDF. Open **Documents** to show how pages and clauses were detected.
3. **1:30–2:15** Ask the initial ownership question. Click the citation to page 1 and find §201(a).
4. **2:15–3:25** Ask the two-page question. Open both page 1 and page 6. Point out §201(a) and §204(a).
5. **3:25–4:05** Ask the royalty-rate question. Show the abstention and the file searched.
6. **4:05–5:00** Show the held-out benchmark and explain one limitation. Use the exam PDF and questions if the professor supplies them.

| Test | Question | Observed result | Time | Input/output tokens |
|---|---|---|---:|---:|
| First question after preparing the index | Under section 201(a), who initially owns copyright in a joint work? | Answer with §201(a), PDF page 1 | 6.92 s | 2,721 / 196 |
| Two-page question | Under section 201(a), who initially owns copyright in a joint work, and under section 204(a), what does a voluntary transfer of copyright ownership require? | Answer with both statutory paragraphs, PDF pages 1 and 6 | 9.11 s | 3,223 / 207 |
| Unanswerable | What royalty rate did Acme Clinic agree to pay for its 2025 photograph licence? | Insufficient evidence | 2.62 s | 1,945 / 5 |
| Repeat the first question | Under section 201(a), who initially owns copyright in a joint work? | Answer with §201(a), PDF page 1 | 6.32 s | 2,721 / 196 |

PDF extraction and index preparation took 23.69 s and are excluded from the question times. This was a local pipeline rehearsal with an existing Ollama service. The schedule includes time to navigate the interface and speak. Timing the full screen-share presentation is a separate rehearsal. The model generated some redundant citations. See `run.json` for the complete recorded answers and timings.
