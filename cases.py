"""Local storage for cases and their cited answers."""
from contextlib import closing, contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from lexic import ABSTAIN, Passage


class CaseStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    passages TEXT NOT NULL, structure TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    name TEXT NOT NULL, pdf BLOB NOT NULL, PRIMARY KEY(case_id, name)
                );
                CREATE TABLE IF NOT EXISTS document_sources (
                    case_id INTEGER NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL,
                    PRIMARY KEY(case_id, name),
                    FOREIGN KEY(case_id, name) REFERENCES documents(case_id, name)
                );
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
                    question TEXT NOT NULL, hits TEXT NOT NULL, result TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS case_answers ON answers(case_id, id);
            """)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db

    def list_cases(self):
        with self.connection() as db:
            return db.execute("SELECT id, name FROM cases ORDER BY id DESC").fetchall()

    def save_case(self, name, docs, passages, structure, sources=None):
        with self.connection() as db:
            case_id = db.execute("INSERT INTO cases(name, passages, structure) VALUES (?, ?, ?)",
                                 (name, json.dumps([asdict(p) for p in passages]), json.dumps(structure))).lastrowid
            db.executemany("INSERT INTO documents VALUES (?, ?, ?)",
                           [(case_id, filename, data) for filename, data in docs.items()])
            db.executemany("INSERT INTO document_sources VALUES (?, ?, ?)",
                           [(case_id, filename, url) for filename, url in (sources or {}).items()])
            return case_id

    def document_sources(self, case_id):
        with self.connection() as db:
            return dict(db.execute("SELECT name, url FROM document_sources WHERE case_id = ?", (case_id,)))

    def open_case(self, case_id):
        with self.connection() as db:
            name, passages, structure = db.execute(
                "SELECT name, passages, structure FROM cases WHERE id = ?", (case_id,)).fetchone()
            docs = dict(db.execute("SELECT name, pdf FROM documents WHERE case_id = ? ORDER BY rowid", (case_id,)))
        return name, docs, [Passage(**p) for p in json.loads(passages)], json.loads(structure)

    def save_answer(self, case_id, question, hits, result):
        with self.connection() as db:
            return db.execute("INSERT INTO answers(case_id, question, hits, result) VALUES (?, ?, ?, ?)",
                              (case_id, question, json.dumps([asdict(p) for p in hits]), json.dumps(result))).lastrowid

    def list_answers(self, case_id):
        with self.connection() as db:
            return db.execute("SELECT id, question FROM answers WHERE case_id = ? ORDER BY id DESC",
                              (case_id,)).fetchall()

    def open_answer(self, case_id, answer_id):
        with self.connection() as db:
            question, hits, result = db.execute(
                "SELECT question, hits, result FROM answers WHERE case_id = ? AND id = ?",
                (case_id, answer_id)).fetchone()
        return question, [Passage(**p) for p in json.loads(hits)], json.loads(result)


def export_answer(case, documents, question, hits, result, sources=None):
    """Build a portable plain-text record from the saved evidence."""
    sources = sources or {}
    lines = [f"LexiSyncAI | {case}", "", "Question", question, "",
             f"Confidence: {result['confidence']}", "",
             "Documents searched", *(f"- {name}" + (f" | {sources[name]}" if name in sources else "") for name in documents), "", "Answer"]
    if not result["claims"]:
        lines.append(ABSTAIN)
    reference = 0
    for claim in result["claims"]:
        lines.extend([claim["text"], ""])
        for citation in claim["evidence"]:
            reference += 1
            passage = hits[citation["id"] - 1]
            label = f"[{reference}] {passage.document} | PDF page {passage.page} | {passage.section}"
            if passage.ocr:
                label += " | OCR transcription"
            lines.extend([label,
                          f"  {citation['quote']}"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
