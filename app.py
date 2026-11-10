from functools import partial
from html import escape
from pathlib import Path
import os
import re
from time import perf_counter

import streamlit as st

from cases import CaseStore, export_answer
from figures import read_figure
from lexic import (ABSTAIN, Index, answer, answer_standalone_questions, ask_model, ingest,
                   lookup_numbered_factor, standalone_questions)
from preview import render_citation
from pdf_import import fetch_pdf
from scan_ocr import read_scan
from version_comparison import compare_versions

st.set_page_config(page_title="LexiSyncAI", layout="wide")
st.html((Path(__file__).with_name("workspace.css")).read_text(encoding="utf-8-sig"))
default_db = Path(__file__).resolve().parent / ".lexisync" / "cases.sqlite3"
store = CaseStore(os.getenv("LEXISYNC_CASE_DB") or default_db)

@st.cache_resource(max_entries=4, show_spinner=False)
def case_index(passages):
    return Index(passages)


def display_case_name(name):
    if not re.match(r"^\d{2}-", name):
        return name
    return re.sub(r"(?<!\d)-|-(?!\d)", " ", name[3:])


with st.sidebar:
    st.html("""
    <div class="lexi-brand">
      <span class="lexi-mark" aria-hidden="true"></span>
      <div><span class="lexi-brand-name">LexiSyncAI</span><span class="lexi-brand-note">Legal research workspace</span></div>
    </div>
    """)
    st.subheader("My cases")
    st.caption("PDFs and question history are saved on this device.")
    saved = dict(store.list_cases())
    if saved:
        if st.session_state.pop("select_new_case", False):
            st.session_state.pop("case_selector", None)
        selected_case = st.selectbox("Choose a case", list(saved), key="case_selector",
                                     format_func=lambda i: f"{display_case_name(saved[i])} / #{i}")
        if selected_case is not None and st.session_state.get("case_id") != selected_case:
            st.session_state.case_id = selected_case
            st.session_state.pop("case_data", None)
            st.session_state.creating_case = False
    history_slot = st.empty()

    if saved:
        st.button("Add a new case", use_container_width=True,
                  on_click=st.session_state.__setitem__, args=("creating_case", True))

if "case_id" not in st.session_state or st.session_state.get("creating_case"):
    with st.container(key="lexi_intake"):
        st.html("""<header class="lexi-case">
            <h1>Add legal documents</h1>
            <p>Choose up to five public PDFs. Once they are ready, you can ask a question about them.</p>
        </header>""")
        uploads = st.file_uploader("Choose PDF files", type="pdf", accept_multiple_files=True,
                                   help="Use the Browse files button to find PDFs on your device.")
        with st.expander("Use official PDF links instead"):
            links = st.text_area("Paste one PDF link per line", max_chars=5000,
                                 help="Use a direct HTTPS download link from a supported official publisher.")
        case = st.text_input("Name this group of documents (optional)", max_chars=120,
                             placeholder="For example, EU data protection",
                             help="If left blank, we use the first PDF filename.")
        use_ocr = st.checkbox("Read scanned pages (OCR)", help="Optional. Uses Windows OCR and the installed Windows language resources.")
        if st.button("Save documents", type="primary", use_container_width=True):
            urls = [line.strip() for line in links.splitlines() if line.strip()]
            if not 1 <= len(uploads) + len(urls) <= 5:
                st.error("Add 1–5 PDFs in total, using uploads, links, or both.")
            elif len({f.name for f in uploads}) != len(uploads):
                st.error("Each PDF needs a different filename. Rename one of the duplicate files and try again.")
            else:
                try:
                    with st.spinner("Getting your documents ready…"):
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
                        passages, structure = ingest(docs, ocr_reader=read_scan if use_ocr else None)
                        if not passages:
                            raise ValueError("No searchable text was found. For scans, enable OCR and check that Windows has OCR support for the document language.")
                        case_id = store.save_case(case_name, docs, passages, structure, sources)
                        st.session_state.case_id = case_id
                        st.session_state.select_new_case = True
                        st.session_state.creating_case = False
                        st.session_state.case_data = (case_name, docs, passages, structure)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not prepare these documents: {exc}")
        if "case_id" in st.session_state:
            st.button("Back to my case", on_click=st.session_state.__setitem__, args=("creating_case", False))
    st.stop()

case_id = st.session_state.case_id
if "case_data" not in st.session_state:
    st.session_state.case_data = store.open_case(case_id)
case, docs, passages, structure = st.session_state.case_data
sources = store.document_sources(case_id)
document_label = "document" if len(docs) == 1 else "documents"
page_label = "page" if len(structure) == 1 else "pages"
st.html(f"""<header class="lexi-case">
    <h1>{escape(display_case_name(case))}</h1>
    <p>Case {case_id} / {len(docs)} {document_label} / {len(structure)} PDF {page_label}</p>
</header>""")
research_tab, documents_tab = st.tabs(["Ask a question", "Documents"])
with documents_tab:
    st.subheader("Case documents")
    for filename in docs:
        st.text(filename)
        if filename in sources:
            st.link_button("Open official source", sources[filename])
    with st.expander("Ask about a chart or figure"):
        st.caption("Choose the PDF page that contains the figure. Compare the experimental answer with the original page.")
        figure_document = st.selectbox("PDF document", list(docs), key=f"figure-document-{case_id}")
        page_count = sum(row["document"] == figure_document for row in structure)
        if page_count:
            with st.form(f"figure-{case_id}"):
                figure_page = st.number_input("PDF page number", min_value=1, max_value=page_count, step=1,
                                              key=f"figure-page-{case_id}-{figure_document}")
                figure_question = st.text_input("What would you like to know about the figure?", max_chars=500)
                figure_submitted = st.form_submit_button("Read the figure")
            if figure_submitted and figure_question.strip():
                try:
                    image, _ = render_citation(docs[figure_document], figure_page, "")
                    st.image(image, caption=f"{figure_document} / PDF page {figure_page}")
                    with st.spinner("Reading the figure…"):
                        interpretation = read_figure(image, figure_question.strip())
                    st.text(interpretation or "The vision model returned no answer.")
                except Exception as exc:
                    st.error(f"Could not read this figure. Check that the local vision model is installed and running. {exc}")
    with st.expander("Page and clause details"):
        if st.button("Re-read documents", help="Refresh page and clause labels while keeping saved answers."):
            try:
                with st.spinner("Re-reading the saved PDFs…"):
                    use_ocr = any(row.get("ocr_status") not in (None, "", "disabled") for row in structure)
                    updated_passages, updated_structure = ingest(docs, ocr_reader=read_scan if use_ocr else None)
                    if not updated_passages:
                        raise ValueError("No searchable text was found.")
                    store.update_document_index(case_id, updated_passages, updated_structure)
                    st.session_state.case_data = (case, docs, updated_passages, updated_structure)
                st.success("Documents refreshed. Ask your question again to use the new evidence.")
                passages, structure = updated_passages, updated_structure
            except Exception as exc:
                st.error(f"Could not re-read these documents: {exc}")
        columns = ("document", "page", "sections", "tables", "image_only", "ocr_status", "empty", "columns")
        headers = ("Document", "PDF page", "Sections", "Tables", "Image only", "OCR", "No text", "Columns")
        rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        for row in structure:
            cells = [str(row.get(column, "")).replace("|", "&#124;").replace("\n", " ") for column in columns]
            rows.append("| " + " | ".join(cells) + " |")
        st.markdown("\n".join(rows))
        if any(row["image_only"] for row in structure):
            st.warning("Image-only pages without recognized text are excluded from search. Check the OCR column for each page.")

with research_tab:
    with st.container(key="lexi_composer"):
        with st.form(f"question-{case_id}", clear_on_submit=True):
            st.caption("Answers use only the documents in this case.")
            question = st.text_input("Type your question", max_chars=1500,
                                     placeholder="For example, what deadline does this document set?")
            submitted = st.form_submit_button("Get answer", type="primary")

    history_key = f"history-{case_id}"
    if submitted and question.strip():
        try:
            question = question.strip()
            started = perf_counter()
            usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            direct = lookup_numbered_factor(question, passages)
            if direct is not None:
                result = direct
                hits = []
                if result["claims"]:
                    citation = result["claims"][0]["evidence"][0]
                    hits = [passages[citation["id"] - 1]]
                    citation["id"] = 1
                retrieved = perf_counter()
            elif comparison := compare_versions(question, passages):
                hits, result = comparison
                retrieved = perf_counter()
            else:
                parts = standalone_questions(question)
                with st.spinner("Searching your documents. The first search can take longer…"):
                    index = case_index(tuple(passages))
                    hits = [index.retrieve(part, k=1)[0] for part in parts] if parts else index.retrieve(question)
                retrieved = perf_counter()
                with st.spinner("Writing and checking the cited answer…"):
                    generate = partial(ask_model, usage=usage)
                    result = (answer_standalone_questions(parts, hits, generate) if parts
                              else answer(question, hits, generate))
            result["usage"] = usage
            result["timing"] = {"retrieval": retrieved - started, "total": perf_counter() - started}
            answer_id = store.save_answer(case_id, question, hits, result)
            st.session_state[history_key] = answer_id
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

    history = dict(store.list_answers(case_id))
    if history:
        with history_slot.container():
            with st.expander("Previous answers"):
                selected_answer = st.selectbox("Choose a past question", history, key=history_key,
                                               format_func=lambda i: f"#{i} · {history[i]}")
                st.download_button("Download case citation audit (CSV)",
                                   data=store.export_citation_audit(case_id, sources),
                                   file_name=f"lexisync-case-{case_id}-citation-audit.csv",
                                   mime="text/csv", on_click="ignore", use_container_width=True)
        question, hits, result = store.open_answer(case_id, selected_answer)
        st.html(f"""<header class="lexi-review-title">
            <h2>Answer</h2><p class="lexi-question">{escape(question)}</p>
        </header>""")
        st.badge(f'Evidence confidence: {result["confidence"].lower()}' if result["claims"] else result["confidence"],
                 color="green" if result["claims"] else "orange")
        if not result["claims"]:
            st.write(ABSTAIN)
            st.caption("Try a question about this case or add a case with documents on the topic.")
            st.caption("Searched " + ", ".join(docs))
        else:
            with st.container(key="lexi_review"):
                left, right = st.columns([1.15, 1], gap="large")
            citations = []
            citation_key = f"citation-{selected_answer}"
            with left, st.container(key="lexi_evidence"):
                st.markdown("#### Key points")
                for point, claim in enumerate(result["claims"], 1):
                    first_source = len(citations)
                    for cite in claim["evidence"]:
                        citations.append((point, hits[cite["id"] - 1], cite["quote"]))
                    count = len(claim["evidence"])
                    source_label = "source" if count == 1 else "sources"
                    st.html(f'<p class="lexi-point"><strong>{point}.</strong><span>{escape(claim["text"])}</span></p>')
                    if count > 1 or len(result["claims"]) > 1:
                        st.button(f"View {count} {source_label} for point {point}", type="tertiary",
                                  key=f"point-{selected_answer}-{point}",
                                  on_click=st.session_state.__setitem__, args=(citation_key, first_source))
            with right, st.container(key="lexi_pdf"):
                st.markdown("#### Supporting evidence")
                selected = 0
                if len(citations) > 1:
                    selected = st.selectbox(
                        "Choose a citation", range(len(citations)),
                        format_func=lambda i: (
                            f"Point {citations[i][0]} · Citation {i + 1} · p. {citations[i][1].page}"
                        ),
                        key=citation_key,
                    )
                _, passage, quote = citations[selected]
                st.caption(f"{passage.document} · PDF page {passage.page} · {passage.section}")
                if passage.ocr:
                    st.caption("This quote was read by OCR. Check it against the original page.")
                if passage.section.startswith("Detected table"):
                    st.caption("Table citation shows the extracted row, column, and cell value.")
                st.html(f'<blockquote class="lexi-excerpt">{escape(quote)}</blockquote>')
                preview, marked = render_citation(docs[passage.document], passage.page, quote)
                st.caption("Original PDF · quote highlighted" if marked else "Original PDF · full page")
                st.image(preview, use_container_width=True)
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
    else:
        st.caption("Your answer and its sources will appear below the question box.")
