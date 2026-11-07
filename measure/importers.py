"""Read tabular exports locally, then require an explicit column mapping."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
import re

from .catalog import lookup, normalize
from .models import Score


class ImportProblem(ValueError):
    pass


@dataclass
class Table:
    title: str
    rows: list[list[str]]


FIELDS = {
    "name": "Subtest / composite / scale", "score": "Score",
    "score_type": "Score type (optional)", "percentile": "Percentile rank",
    "ci": "Confidence interval", "category": "Descriptive category",
    "age_eq": "Age equivalent", "grade_eq": "Grade equivalent", "raw_score": "Raw score",
}
HEADER_ALIASES = {
    "name": ("name", "scale", "subtest", "composite", "composite subtest", "composite scale", "test", "measure", "index"),
    "score": ("score", "standard score", "scaled score", "t score", "t", "ss", "standard scaled score"),
    "score_type": ("score type", "type", "metric"),
    "percentile": ("percentile", "percentile rank", "pr"),
    "ci": ("confidence interval", "95 conf interval", "90 conf interval", "95 confidence interval", "90 confidence interval", "95 ci", "90 ci", "ci"),
    "category": ("category", "descriptive category", "descriptive classification", "qualitative description", "classification", "descriptor"),
    "age_eq": ("age eq", "age equivalent"), "grade_eq": ("grade eq", "grade equivalent"),
    "raw_score": ("raw", "raw score"),
}


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value)).strip()


def _rectangular(rows) -> list[list[str]]:
    result = [[clean(value) for value in row] for row in rows]
    result = [row for row in result if any(row)]
    width = max((len(row) for row in result), default=0)
    return [row + [""] * (width - len(row)) for row in result]


def parse_delimited(text: str) -> list[list[str]]:
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ImportProblem("The table is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;")
        reader = csv.reader(io.StringIO(text), dialect)
        rows = _rectangular(reader)
    except csv.Error:
        rows = _rectangular(line.split("\t") for line in text.splitlines())
    if not rows or len(rows[0]) < 2:
        raise ImportProblem("No columns found. Paste a table from Excel or use a CSV/TSV file.")
    return rows


def read_tables(path: str | Path) -> list[Table]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="cp1252")
        return [Table(path.name, parse_delimited(text))]
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            return [Table(sheet.title, _rectangular(sheet.iter_rows(values_only=True))) for sheet in workbook if sheet.max_row]
        finally:
            workbook.close()
    if suffix == ".docx":
        from docx import Document
        document = Document(path)
        tables = [Table(f"Table {i + 1}", _rectangular([cell.text for cell in row.cells] for row in table.rows))
                  for i, table in enumerate(document.tables)]
        if not tables:
            raise ImportProblem("This Word file has no tables. Use a document containing a score table.")
        return tables
    if suffix == ".pdf":
        import pdfplumber
        result = []
        with pdfplumber.open(path) as document:
            for page_number, page in enumerate(document.pages, 1):
                extracted = page.extract_tables()
                if not extracted:
                    extracted = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
                for i, table in enumerate(extracted, 1):
                    rows = _rectangular(table)
                    if len(rows) > 1 and len(rows[0]) > 1:
                        result.append(Table(f"Page {page_number}, table {i}", rows))
        if not result:
            raise ImportProblem("No readable table found. Scanned PDFs need OCR; export a Word or Excel score table instead.")
        return result
    raise ImportProblem("Supported score tables: CSV, TSV, TXT, XLSX, DOCX, and text-based PDF.")


def header_mapping(row: list[str]) -> dict[str, int]:
    mapping = {}
    for field, aliases in HEADER_ALIASES.items():
        for index, heading in enumerate(row):
            if normalize(heading) in aliases:
                mapping[field] = index
                break
    return mapping


def guess_header(rows: list[list[str]]) -> int:
    return max(range(min(12, len(rows))), key=lambda i: len(header_mapping(rows[i])), default=0)


def _optional(value: str) -> str:
    return "" if value.strip() in ("", "-", "--", "—", "–", "N/A", "n/a") else value.strip()


def _score_type(value: str) -> str:
    options = {"ss": "standard", "standard": "standard", "standard score": "standard",
               "scaled": "scaled", "scaled score": "scaled", "t": "t", "t score": "t"}
    key = normalize(value)
    if key not in options:
        raise ImportProblem(f"Unknown score type {value!r}. Use standard, scaled, or t.")
    return options[key]


def scores_from_table(table: Table, mapping: dict[str, int], test: str,
                      header_row: int = 0, default_type: str = "auto",
                      source: str = "Imported table") -> tuple[list[Score], list[str]]:
    if "name" not in mapping or "score" not in mapping:
        raise ImportProblem("Map both the measure name and score columns.")
    if mapping["name"] == mapping["score"]:
        raise ImportProblem("Measure name and score must use different columns.")
    scores, warnings, seen = [], [], {}
    for index, values in enumerate(table.rows[header_row + 1:], header_row + 2):
        def cell(key):
            column = mapping.get(key)
            return _optional(values[column]) if column is not None and column < len(values) else ""
        label, value = cell("name"), cell("score")
        if not label or not value:
            # Section headings are common, but expose skipped rows for review.
            if label:
                warnings.append(f"Row {index}: skipped {label!r} because the score is blank.")
            continue
        if normalize(label) in HEADER_ALIASES["name"] and normalize(value) in HEADER_ALIASES["score"]:
            continue
        try:
            score_value = float(value)
        except ValueError:
            raise ImportProblem(f"Row {index} ({label}): {value!r} is not a numeric score. Check the mapped column.") from None
        # Trailing superscript/footnote markers are removed only when the name then resolves.
        known = lookup(test, label)
        if not known:
            candidate = re.sub(r"[\d*†‡]+$", "", label).strip()
            known = lookup(test, candidate)
        name = known.name if known else label
        explicit_type = cell("score_type")
        if explicit_type:
            kind = _score_type(explicit_type)
        elif default_type != "auto":
            kind = default_type
        elif known:
            kind = known.kind
        elif test == "PAI":
            kind = "t"
        else:
            header = normalize(table.rows[header_row][mapping["score"]])
            kind = "scaled" if "scaled" in header else "t" if header in ("t", "t score") else "standard"
            warnings.append(f"Row {index}: {label!r} is a custom name; verify its {kind} score type.")
        if known and kind != known.kind:
            warnings.append(f"Row {index}: {name} usually uses {known.kind} scores; confirm the selected {kind} metric.")
        record = Score(name=name, score=score_value, score_type=kind,
                       percentile=cell("percentile"), ci=cell("ci"), category=cell("category"),
                       age_eq=cell("age_eq"), grade_eq=cell("grade_eq"), raw_score=cell("raw_score"),
                       aliases=[label] if label != name else [], source=f"{source} · {table.title} · row {index}")
        errors = record.validate()
        if errors:
            raise ImportProblem("\n".join(errors))
        key = normalize(name)
        if key in seen:
            old = seen[key]
            fields = ("score", "score_type", "percentile", "ci", "category", "age_eq", "grade_eq", "raw_score")
            if any(getattr(old, f) != getattr(record, f) for f in fields):
                raise ImportProblem(f"Conflicting duplicate scores for {name}. Import one norm group or table at a time.")
            warnings.append(f"Row {index}: repeated {name} row was merged.")
            continue
        seen[key] = record
        scores.append(record)
    if not scores:
        raise ImportProblem("No scores imported. Check the header row and the two required columns.")
    return scores, warnings
