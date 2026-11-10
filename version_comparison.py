"""Match a documented substitution to the wording in two statutory editions."""
import re


SECTION = re.compile(r"(?:\bsection\s+|§\s*)(\d+[a-z]?)\s*\(([a-z0-9]+)\)", re.I)
HEADING = re.compile(r"§\s*(\d+[a-z]?)", re.I)
AMENDMENT = re.compile(
    r"\bAMENDMENTS\s+(\d{4})[—–-]\s*Subsecs?\.\s+"
    r"((?:\([a-z0-9]+\)(?:,\s*)?)+)\.\s*"
    r"(Pub\. L\. \d+[–-]\d+),\s+[^.]+?\bsubstituted\s+"
    r"[‘’“”\"]+([^‘’“”\"]+)[‘’“”\"]+\s+for\s+[‘’“”\"]+([^‘’“”\"]+)[‘’“”\"]+\.",
    re.I,
)


def normalized(text):
    return re.sub(r"\s+", "", text.casefold().replace("’", "'"))


def mask_substitution(text, term):
    matches = list(re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I))
    if len(matches) != 1:
        return None
    match = matches[0]
    return normalized(text[:match.start()]), normalized(text[match.end():])


def compare_versions(question, passages):
    """Return cited claims when a scoped amendment exactly explains the difference."""
    references = {(number.lower(), item.lower()) for number, item in SECTION.findall(question)}
    comparison, separator, amendment = question.strip().rpartition(", and ")
    if (not separator or len(references) != 1 or "?" in comparison
            or not re.match(r"^(?:how (?:do|does|did)\b.+\bdiffer\b|compare\b)", comparison, re.I)
            or not re.fullmatch(r"(?:what|which) amendment (?:explains|accounts for|made|caused) "
                                r"(?:this|the) (?:difference|change)\??", amendment, re.I)):
        return None
    number, item = references.pop()
    label = f"§{number} ({item})"
    clauses = {}
    headings = {}
    notes = []
    for passage in passages:
        if passage.ocr:
            continue
        if heading := HEADING.fullmatch(passage.section):
            headings[passage.document] = heading[1].lower()
        if passage.section.lower() == label and passage.text.lower().startswith(f"({item}) "):
            clauses.setdefault(passage.document, []).append(passage)
        if (headings.get(passage.document) == number and passage.section.casefold() == "editorial notes"
                and (match := AMENDMENT.search(passage.text)) and f"({item})" in match[2].lower()):
            notes.append((passage, match))
    if len(clauses) != 2:
        return None
    matches = []
    for note, match in notes:
        if note.document not in clauses:
            continue
        year, _, law, new_term, old_term = match.groups()
        original = next(doc for doc in clauses if doc != note.document)
        for old in clauses[original]:
            masked_old = mask_substitution(old.text, old_term)
            if masked_old is None:
                continue
            for new in clauses[note.document]:
                if masked_old == mask_substitution(new.text, new_term):
                    matches.append((old, new, note, match, year, law, old_term, new_term))
    if len(matches) != 1:
        return None
    old, new, note, match, year, law, old_term, new_term = matches[0]
    return [old, new, note], {
        "confidence": "HIGH",
        "claims": [
            {"text": f"In §{number}({item}), {old.document} uses “{old_term}” where "
                     f"{new.document} uses “{new_term}”. The cited clauses show the wording in context.",
             "evidence": [{"id": 1, "quote": old.text}, {"id": 2, "quote": new.text}]},
            {"text": f"The editorial note attributes this substitution to {law} ({year}).",
             "evidence": [{"id": 3, "quote": match.group()}]},
        ],
        "trace": ["Matched the two cited clauses to a subsection-specific amendment note."],
    }
