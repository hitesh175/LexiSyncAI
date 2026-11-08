# LexiSyncAI architecture

[One-page architecture diagram](architecture.svg)

## Implemented local app

| Responsibility | Module | Output |
|---|---|---|
| Create or reopen a case | `app.py`, `pdf_import.py`, `cases.py` | A saved case with PDFs, original links when supplied, and searchable passages |
| Extract and index | `lexic.py` | Page and section labels, scan flags, basic table data, BM25 and dense indexes |
| Retrieve evidence | `lexic.py` | Fused and reranked passages, including explicitly referenced clauses when matched |
| Draft and check the answer | `lexic.py`, Ollama | Exact source excerpts, a verifier result, and at most one repair attempt |
| Review and save | `app.py`, `preview.py`, `cases.py` | Original PDF page, quote highlight where available, answer history and export |
| Evaluate | `evaluate.py`, `RESULTS.md` | Retrieval recall, manual accuracy and citation precision, abstention and latency |

## Proposed Vercel Workflow extension

This is a design for a future hosted version. The local Python app currently runs indexing and question answering in the app process.

1. **Start ingestion.** An authenticated API validates the case and uses `start()` to return a run ID. The client can poll or reconnect using that ID. Pass document references across step boundaries and store PDF bytes outside the workflow log.
2. **Ingest in durable steps.** Validate or fetch PDFs, call a Python extraction worker, then save passages and build a versioned index. Use a case ID and source version as the write key so a retry cannot create duplicate case data. Mark the case ready only after the index is available.
3. **Answer in durable steps.** Retrieve and rerank evidence, draft from numbered excerpts, validate and verify, and persist either the answer or the abstention. An evidence repair stays capped at one. Temporary worker or network failures can retry separately. Invalid inputs fail without retries.
4. **Reconnect and observe.** Report step names, elapsed times and result status. A future hosted setup needs shared persistent storage and a reachable Python worker and model endpoint. The current device-local SQLite database and Ollama endpoint belong to the local deployment.

The workflow function would coordinate the stages. Step functions would perform network and storage operations and record progress. [Vercel Workflow documentation](https://vercel.com/docs/workflows) · [Workflow SDK foundations](https://workflow-sdk.dev/docs/foundations/workflows-and-steps)

