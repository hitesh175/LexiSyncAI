from contextlib import closing
from pathlib import Path
import os

import streamlit as st
import pypdfium2 as pdfium

from cases import CaseStore, export_answer
from lexic import ABSTAIN, Index, answer, ingest

st.set_page_config(page_title="LexiSyncAI", layout="wide")
st.title("LexiSyncAI")
st.caption("Evidence-grounded analysis of public legal PDFs")
default_db = Path(__file__).resolve().parent / ".lexisync" / "cases.sqlite3"
store = CaseStore(os.getenv("LEXISYNC_CASE_DB") or default_db)

with st.sidebar:
    saved = dict(store.list_cases())
    if saved:
        selected_case = st.selectbox("Saved cases", saved, format_func=lambda i: f"{saved[i]} · #{i}")
        if st.button("Open case"):
            st.session_state.case_id = selected_case
            st.session_state.pop("case_data", None)
            st.session_state.pop("index", None)
    with st.expander("New case", expanded=not saved):
        case = st.text_input("Case name", max_chars=120)
        uploads = st.file_uploader("Upload public PDFs", type="pdf", accept_multiple_files=True)
        if st.button("Index and save case"):
            if not case.strip() or not 1 <= len(uploads) <= 5 or len({f.name for f in uploads}) != len(uploads):
                st.error("Enter a case name and select 1–5 uniquely named PDFs.")
            else:
                try:
                    with st.spinner("Extracting pages and building the index…"):
                        docs = {f.name: f.getvalue() for f in uploads}
                        passages, structure = ingest(docs)
                        index = Index(passages)
                        case_id = store.save_case(case.strip(), docs, passages, structure)
                        st.session_state.case_id = case_id
                        st.session_state.case_data = (case.strip(), docs, passages, structure)
                        st.session_state.index = index
                    st.rerun()
                except Exception as exc:
                    st.error(f"Indexing failed: {exc}")

if "case_id" not in st.session_state:
    st.info("Open a saved case or create a case with public PDFs.")
    st.stop()

case_id = st.session_state.case_id
if "case_data" not in st.session_state:
    st.session_state.case_data = store.open_case(case_id)
case, docs, passages, structure = st.session_state.case_data
st.subheader(case)
st.caption(f"Case #{case_id} · {len(docs)} document(s) · {len(structure)} PDF pages")
with st.expander("Detected document structure"):
    columns = ("document", "page", "sections", "tables", "image_only", "empty", "columns")
    headers = ("Document", "PDF page", "Sections", "Tables", "Image only", "No text", "Columns")
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in structure:
        cells = [str(row[column]).replace("|", "&#124;").replace("\n", " ") for column in columns]
        rows.append("| " + " | ".join(cells) + " |")
    st.markdown("\n".join(rows))
    if any(row["image_only"] for row in structure):
        st.warning("Image-only pages are shown above. Their text is excluded from retrieval.")

with st.form(f"question-{case_id}", clear_on_submit=True):
    question = st.text_input("Ask about the indexed documents", max_chars=1500)
    submitted = st.form_submit_button("Find evidence and answer")

history_key = f"history-{case_id}"
if submitted and question.strip():
    try:
        with st.spinner("Retrieving, drafting and checking evidence…"):
            if "index" not in st.session_state:
                st.session_state.index = Index(passages)
            hits = st.session_state.index.retrieve(question.strip())
            result = answer(question.strip(), hits)
            answer_id = store.save_answer(case_id, question.strip(), hits, result)
            st.session_state[history_key] = answer_id
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")

history = dict(store.list_answers(case_id))
if history:
    selected_answer = st.selectbox("Question history", history, key=history_key,
                                   format_func=lambda i: f"#{i} · {history[i]}")
    question, hits, result = store.open_answer(case_id, selected_answer)
    st.text(question)
    st.badge(result["confidence"])
    st.download_button("Download answer and citations",
                       data=export_answer(case, docs, question, hits, result),
                       file_name=f"lexisync-case-{case_id}-answer-{selected_answer}.txt",
                       mime="text/plain; charset=utf-8")
    if not result["claims"]:
        st.write(ABSTAIN)
        st.caption("Searched " + ", ".join(docs))
    else:
        left, right = st.columns(2)
        citations = []
        with left:
            for claim in result["claims"]:
                st.text(claim["text"])
                for cite in claim["evidence"]:
                    p = hits[cite["id"] - 1]
                    label = f'{p.document} · PDF p. {p.page} · {p.section}'
                    st.caption(label)
                    st.text(cite["quote"])
                    citations.append((label, p))
        with right:
            selected = st.selectbox("Open cited PDF page", range(len(citations)),
                                    format_func=lambda i: citations[i][0], key=f"citation-{selected_answer}")
            p = citations[selected][1]
            with closing(pdfium.PdfDocument(docs[p.document])) as pdf:
                with closing(pdf[p.page - 1]) as page:
                    with closing(page.render(scale=1.4)) as bitmap:
                        preview = bitmap.to_pil().copy()
            st.image(preview, use_container_width=True)


