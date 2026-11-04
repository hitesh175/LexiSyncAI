import streamlit as st
import pypdfium2 as pdfium

from lexic import ABSTAIN, Index, answer, ingest

st.set_page_config(page_title="LexiSyncAI", layout="wide")
st.title("LexiSyncAI")
st.caption("Evidence-grounded analysis of public legal PDFs")
with st.sidebar:
    case = st.text_input("Case name", "Copyright study")
    uploads = st.file_uploader("Upload public PDFs", type="pdf", accept_multiple_files=True)
    if st.button("Index case"):
        if not case.strip() or not 1 <= len(uploads) <= 5 or len({f.name for f in uploads}) != len(uploads):
            st.error("Enter a case name and select 1–5 uniquely named PDFs. Use 2–5 for the assignment bundle.")
        else:
            try:
                with st.spinner("Extracting pages and building the index…"):
                    docs = {f.name: f.getvalue() for f in uploads}
                    passages, structure = ingest(docs)
                    st.session_state.active = (case, docs, structure, Index(passages))
                    st.session_state.pop("result", None)
            except Exception as exc:
                st.error(f"Indexing failed: {exc}")

if "active" not in st.session_state:
    st.info("Name a case and index your PDFs to begin.")
    st.stop()

case, docs, structure, index = st.session_state.active
st.subheader(case)
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

with st.form("question"):
    question = st.text_input("Ask about the indexed documents", max_chars=1500)
    submitted = st.form_submit_button("Find evidence and answer")

if submitted and question.strip():
    st.session_state.pop("result", None)
    try:
        with st.spinner("Retrieving, drafting and checking evidence…"):
            hits = index.retrieve(question)
            st.session_state.result = (question, hits, answer(question, hits))
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")

if "result" in st.session_state:
    question, hits, result = st.session_state.result
    st.text(question)
    st.badge(result["confidence"])
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
                                    format_func=lambda i: citations[i][0])
            p = citations[selected][1]
            with pdfium.PdfDocument(docs[p.document]) as pdf:
                page = pdf[p.page - 1]
                bitmap = page.render(scale=1.4)
                st.image(bitmap.to_pil().copy(), use_container_width=True)
                bitmap.close()
                page.close()

