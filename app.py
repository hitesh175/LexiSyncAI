from functools import partial
from html import escape
from pathlib import Path
import os
from time import perf_counter

import streamlit as st

from cases import CaseStore, export_answer
from lexic import ABSTAIN, Index, answer, ask_model, ingest
from preview import render_citation
from pdf_import import fetch_pdf

st.set_page_config(page_title="LexiSyncAI", layout="wide")
st.html((Path(__file__).with_name("workspace.css")).read_text(encoding="utf-8-sig"))
default_db = Path(__file__).resolve().parent / ".lexisync" / "cases.sqlite3"
store = CaseStore(os.getenv("LEXISYNC_CASE_DB") or default_db)

@st.cache_resource(max_entries=4, show_spinner=False)
def case_index(passages):
    return Index(passages)


with st.sidebar:
    st.html("""
    <div class="lexi-brand">
      <span class="lexi-mark" aria-hidden="true"></span>
      <div><span class="lexi-brand-name">LexiSyncAI</span><span class="lexi-brand-note">Legal research workspace</span></div>
    </div>
    """)
    st.subheader("Case library")
    st.caption("PDFs and question history are saved on this device.")
    saved = dict(store.list_cases())
    if saved:
        selected_case = st.selectbox("Saved cases", saved, format_func=lambda i: f"{saved[i]} · #{i}")
        if st.button("Open case", use_container_width=True):
            st.session_state.case_id = selected_case
            st.session_state.pop("case_data", None)

    with st.expander("New case", expanded=not saved):
        case = st.text_input("Case name (optional)", max_chars=120,
                             help="Leave blank to use the first PDF filename.")
        uploads = st.file_uploader("Upload public PDFs", type="pdf", accept_multiple_files=True)
        links = st.text_area("Official PDF links (optional)", max_chars=5000,
                             help="One direct HTTPS PDF link per line. Supported publishers include EUR-Lex, EDPB, GovInfo, UK legislation and German federal legislation.")
        if st.button("Index and save case", type="primary", use_container_width=True):
            urls = [line.strip() for line in links.splitlines() if line.strip()]
            if not 1 <= len(uploads) + len(urls) <= 5:
                st.error("Add 1–5 PDFs in total, using uploads, links, or both.")
            elif len({f.name for f in uploads}) != len(uploads):
                st.error("Each PDF needs a different filename. Rename one of the duplicate files and try again.")
            else:
                try:
                    with st.spinner("Importing PDFs and preparing the case…"):
                        docs = {f.name: f.getvalue() for f in uploads}
                        sources = {}
                        for url in urls:
                            filename, content = fetch_pdf(url)
                            stem = Path(filename).stem
                            suffix = 2
                            while filename in docs:
                                filename = f"{stem}-{suffix}.pdf"
                                suffix += 1
                            docs[filename] = content
                            sources[filename] = url
                        case_name = case.strip() or Path(next(iter(docs))).stem[:120] or "Untitled case"
                        passages, structure = ingest(docs)
                        if not passages:
                            raise ValueError("No searchable text was found in these PDFs.")
                        case_index(tuple(passages))
                        case_id = store.save_case(case_name, docs, passages, structure, sources)
                        st.session_state.case_id = case_id
                        st.session_state.case_data = (case_name, docs, passages, structure)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Indexing failed: {exc}")

if "case_id" not in st.session_state:
    st.html("""
    <section class="lexi-empty">
      <h1>Research a case</h1>
      <p>Open a saved case or start with public legal documents. Review each answer alongside the passage it cites.</p>
      <ol>
        <li>Add up to five PDFs using uploads or official links.</li>
        <li>Ask a question about the documents.</li>
        <li>Open a numbered citation to inspect the original page.</li>
      </ol>
    </section>
    """)
    st.stop()

case_id = st.session_state.case_id
if "case_data" not in st.session_state:
    st.session_state.case_data = store.open_case(case_id)
case, docs, passages, structure = st.session_state.case_data
sources = store.document_sources(case_id)
document_label = "document" if len(docs) == 1 else "documents"
page_label = "page" if len(structure) == 1 else "pages"
st.html(f"""<header class="lexi-case">
    <h1>{escape(case)}</h1>
    <p>Case {case_id} / {len(docs)} {document_label} / {len(structure)} PDF {page_label}</p>
</header>""")
with st.expander("Detected document structure"):
    columns = ("document", "page", "sections", "tables", "image_only", "empty", "columns")
    headers = ("Document", "PDF page", "Sections", "Tables", "Image only", "No text", "Columns")
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in structure:
        cells = [str(row[column]).replace("|", "&#124;").replace("\n", " ") for column in columns]
        rows.append("| " + " | ".join(cells) + " |")
    st.markdown("\n".join(rows))
    for filename, url in sources.items():
        st.link_button(f"Official source for {filename}", url)
    if any(row["image_only"] for row in structure):
        st.warning("Image-only pages are shown above. Their text is excluded from retrieval.")

with st.container(key="lexi_composer"):
    with st.form(f"question-{case_id}", clear_on_submit=True):
        question = st.text_input("Ask about the indexed documents", max_chars=1500,
                                 placeholder="Ask about a clause, obligation, deadline, or comparison")
        submitted = st.form_submit_button("Find evidence and answer", type="primary")

history_key = f"history-{case_id}"
if submitted and question.strip():
    try:
        with st.spinner("Retrieving, drafting and checking evidence…"):
            started = perf_counter()
            index = case_index(tuple(passages))
            hits = index.retrieve(question.strip())
            retrieved = perf_counter()
            usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            result = answer(question.strip(), hits, generate=partial(ask_model, usage=usage))
            result["usage"] = usage
            result["timing"] = {"retrieval": retrieved - started, "total": perf_counter() - started}
            answer_id = store.save_answer(case_id, question.strip(), hits, result)
            st.session_state[history_key] = answer_id
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")

history = dict(store.list_answers(case_id))
if history:
    selected_answer = st.selectbox("Question history", history, key=history_key,
                                   format_func=lambda i: f"#{i} · {history[i]}")
    question, hits, result = store.open_answer(case_id, selected_answer)
    st.html(f"""<header class="lexi-review-title">
        <h2>Answer review</h2><p class="lexi-question">{escape(question)}</p>
    </header>""")
    status_col, export_col = st.columns([2, 1], vertical_alignment="center")
    with status_col:
        st.badge(result["confidence"], color="green" if result["claims"] else "orange")
    with export_col:
        st.download_button("Download answer and citations",
                           data=export_answer(case, docs, question, hits, result, sources),
                           file_name=f"lexisync-case-{case_id}-answer-{selected_answer}.txt",
                           mime="text/plain; charset=utf-8", use_container_width=True)
    if result.get("trace") or result.get("timing"):
        with st.expander("Analysis details"):
            if timing := result.get("timing"):
                st.caption(f"Retrieval {timing['retrieval']:.2f} s  |  Answer and checks {timing['total'] - timing['retrieval']:.2f} s")
            if usage := result.get("usage"):
                st.caption(f"{usage['calls']} model calls  |  {usage['input_tokens']:,} input tokens  |  {usage['output_tokens']:,} output tokens")
            for step in result.get("trace", []):
                st.text(step)
    if not result["claims"]:
        st.write(ABSTAIN)
        st.caption("Searched " + ", ".join(docs))
    else:
        with st.container(key="lexi_review"):
            left, right = st.columns([1.15, 1], gap="large")
        citations = []
        citation_key = f"citation-{selected_answer}"
        with left, st.container(key="lexi_evidence"):
            st.markdown("#### Claims and evidence")
            for claim in result["claims"]:
                st.write(claim["text"])
                for cite in claim["evidence"]:
                    p = hits[cite["id"] - 1]
                    source_index = len(citations)
                    label = f'[{source_index + 1}] {p.document} · PDF p. {p.page} · {p.section}'
                    citations.append((label, p, cite["quote"]))
                    st.button(label, key=f"source-{selected_answer}-{source_index}",
                              on_click=st.session_state.__setitem__, args=(citation_key, source_index))
                    st.html(f'<blockquote class="lexi-excerpt">{escape(cite["quote"])}</blockquote>')
        with right, st.container(key="lexi_pdf"):
            st.markdown("#### Original PDF")
            selected = st.selectbox("Open cited PDF page", range(len(citations)),
                                    format_func=lambda i: f"Reference {i + 1} / PDF page {citations[i][1].page}",
                                    key=citation_key)
            _, passage, quote = citations[selected]
            st.caption(f"{passage.document} / {passage.section}")
            preview, marked = render_citation(docs[passage.document], passage.page, quote)
            st.caption("Quoted text highlighted" if marked else "Full page shown · quote region unavailable")
            st.image(preview, use_container_width=True)








