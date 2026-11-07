# LexiSyncAI

A local research prototype that answers questions about public legal PDFs and shows the passage and PDF page behind each claim.

## Run on Windows

Double-click **Launch LexiSyncAI.cmd**. Keep the launcher window open while using the app. On a fresh Windows machine, install Python 3.11 or 3.12 and Ollama first. The launcher prepares the local environment and downloads missing dependencies and the Ollama model on first use. The retrieval models download when you first index a case.

### Manual setup

Install Python 3.11 or 3.12 and Ollama. Start Ollama and make the model available with `ollama pull kamekichi128/qwen3-4b-instruct-2507:latest`. The default matches the model available on the development machine. Set `OLLAMA_MODEL` to use another instruction model with JSON support.

From this folder in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501. Upload the two PDFs in `data`, name the case, and select **Index case**. First indexing downloads the retrieval models from Hugging Face. The app keeps the case in the browser session. The one-document option supports the unseen-PDF demo.

With Docker Desktop and a running host Ollama service, run `docker compose up --build`. The container connects to the host via `host.docker.internal`. The native Python setup is the direct route if the host service is inaccessible from Docker.

## Architecture

Open [the one-page architecture diagram](architecture.svg). Ingestion tracks numbered headings and subclauses, splits unusually long passages, preserves page boundaries, detects simple ruled tables, and flags image-only pages. The column heuristic detects pages with a central gutter. The sample GovInfo running header is removed. Complex layouts, footnotes, and spanning tables can need manual review. Image-only pages are flagged for review and have no OCR pass.

BM25 preserves lexical signals such as clause numbers. MiniLM embeddings retrieve paraphrases. Reciprocal rank fusion merges the top 30 candidates from each ranker, then a cross-encoder scores question–passage pairs. The generator sees ten reranked passages with immutable source IDs. A deterministic check requires an exact excerpt from each cited passage. A second model pass checks support, coverage, arithmetic, and attribution. Unsupported drafts abstain. Backend errors are shown separately. Confidence labels describe the verifier's assessment and are uncalibrated. PDF pages are numbered from 1 within each file.

## Evaluation

The 15-question fixture has nine factual, three cross-document, and three unanswerable questions. It uses the 2023 U.S. Code extracts below as a fixed research corpus. Gold labels use PDF filename, page and section. The questions are used for evaluation with frozen model weights. They share a small corpus, so results describe this fixture.

```powershell
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe evaluate.py
```

Use `--retrieval-only` to skip generation. The script reports clause recall at 1, 5 and 10 for BM25, dense, fusion and hybrid with reranking. Complete gold coverage at 10 tracks whether every required hop is present. Dense versus reranked hybrid holds the generator and ten-passage context limit constant. End-to-end runs report mean latency and both true and false abstentions. Warm models first for a separate steady-state timing run. The index timer includes model startup. For manual grading, open each review CSV, mark answer correctness as 0 or 1, and count citations that substantively support their attached claims. A correct refusal gets 1 on an unanswerable item. Calculate correctness across all 15 items and citation precision as supported citations divided by total emitted citations. Record the reviewer and hardware with the results.

- [GovInfo 2023 U.S. Code, 17 USC §106](https://www.govinfo.gov/content/pkg/USCODE-2023-title17/pdf/USCODE-2023-title17-chap1-sec106.pdf)
- [GovInfo 2023 U.S. Code, 17 USC §107](https://www.govinfo.gov/content/pkg/USCODE-2023-title17/pdf/USCODE-2023-title17-chap1-sec107.pdf)

The extracts include adjacent sections and legislative notes. Use the statutory text when the question asks what the statute says. The included PDFs are research snapshots.

See [the five-minute demo outline](DEMO.md) for the walkthrough and theory prompts.

See [measured benchmark results](RESULTS.md).



## Saved cases

Create a case with **Index and save case**. Use **Saved cases** and **Open case** after restarting. Question history includes abstentions, exact evidence excerpts, and access to the original cited pages. The first new question after reopening a case rebuilds the search index from saved passages.

PDFs and answers are stored in `.lexisync/cases.sqlite3` in the project folder. Back up this file while the app is closed. Keep the app on localhost and use public documents. For a custom database location, set `LEXISYNC_CASE_DB`. For Docker, mount a persistent volume at `/app/.lexisync`.

Select a saved answer and choose **Download answer and citations** for a plain-text record of the question, searched files, answer, and quoted evidence.

See [assignment coverage](RUBRIC.md) for the rubric, verified features, and open bonus items.

## Import official PDF links

In **New case**, enter one direct HTTPS PDF URL per line in **Official PDF links**. You can mix links and uploads, up to five files total. The app supports EUR-Lex, EDPB, GovInfo, UK legislation and the listed German federal publishers. Linked PDFs are limited to 25 MB each. If a publisher serves a web page or blocks downloads, save the PDF and upload it. The source link is retained with the case and included in answer exports.

The app keeps up to four prepared search indexes in memory until restart and asks Ollama to keep the local model loaded for 30 minutes. Under **Analysis details**, retrieval time includes index preparation on a cold case. Model time includes generation, verification and any repair.
