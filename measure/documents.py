"""Local template I/O and run-aware Word edits."""
from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path

from .engine import Renderer, RenderResult, Edit


@dataclass
class Template:
    text: str
    docx_bytes: bytes | None = None
    original_text: str = ""


def paragraphs_in(container):
    """Yield body/table paragraphs in their document order, including nested tables."""
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    for child in container._element:
        if child.tag == qn("w:p"):
            yield Paragraph(child, container)
        elif child.tag == qn("w:tbl"):
            table = Table(child, container)
            seen = set()
            for row in table.rows:
                for cell in row.cells:
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield from paragraphs_in(cell)


def document_paragraphs(document):
    from docx.document import _Body
    yield from paragraphs_in(_Body(document._element.body, document))
    # A linked header/footer may be exposed by multiple sections; edit it once.
    seen = set()
    for section in document.sections:
        for container in (section.header, section.first_page_header, section.even_page_header,
                          section.footer, section.first_page_footer, section.even_page_footer):
            if not container._has_definition:
                continue
            if container._element not in seen:
                seen.add(container._element)
                yield from paragraphs_in(container)


def body_text(document) -> str:
    from docx.document import _Body
    return "\n".join(paragraph.text for paragraph in paragraphs_in(_Body(document._element.body, document)))


def load_template(path: str | Path) -> Template:
    path = Path(path)
    if path.suffix.lower() == ".docx":
        from docx import Document
        payload = path.read_bytes()
        text = body_text(Document(io.BytesIO(payload)))
        return Template(text, payload, text)
    if path.suffix.lower() in (".txt", ".md"):
        text = path.read_text(encoding="utf-8-sig")
        return Template(text, original_text=text)
    raise ValueError("Report templates must be Word (.docx), text (.txt), or Markdown (.md).")


def apply_paragraph_edits(paragraph, edits: list[Edit]) -> None:
    """Retain untouched runs, styles, tables, and paragraph properties.

    A replacement spanning several runs inherits the first run's text formatting.
    Existing hyperlinks are not rewritten: such templates require text export.
    """
    runs = paragraph.runs
    if not edits:
        return
    text = paragraph.text
    if "".join(run.text for run in runs) != text:
        raise ValueError("This paragraph contains a hyperlink or field that cannot be edited safely. Use plain-text export or a simpler template.")
    for edit in reversed(edits):
        positions, cursor = [], 0
        for run in runs:
            positions.append((cursor, cursor + len(run.text)))
            cursor += len(run.text)
        if not runs:
            paragraph.add_run(edit.replacement)
            runs = paragraph.runs
            continue
        if edit.start == edit.end:
            index = next((i for i, (start, end) in enumerate(positions) if start < edit.start <= end), 0)
            offset = edit.start - positions[index][0]
            value = runs[index].text
            runs[index].text = value[:offset] + edit.replacement + value[offset:]
            continue
        first = next(i for i, (start, end) in enumerate(positions) if start <= edit.start < end)
        last = next(i for i, (start, end) in enumerate(positions) if start < edit.end <= end)
        start_offset, end_offset = edit.start - positions[first][0], edit.end - positions[last][0]
        prefix, suffix = runs[first].text[:start_offset], runs[last].text[end_offset:]
        if first == last:
            runs[first].text = prefix + edit.replacement + suffix
        else:
            runs[first].text = prefix + edit.replacement
            for i in range(first + 1, last):
                runs[i].text = ""
            runs[last].text = suffix


def _unsupported_parts(document) -> bool:
    from docx.oxml.ns import qn
    # Word text boxes, tracked changes, and content controls are absent from
    # python-docx's paragraph traversal. Reject preservation rather than omit.
    unsupported = {qn("w:txbxContent"), qn("w:ins"), qn("w:del"), qn("w:sdt")}
    for part in document.part.package.parts:
        element = getattr(part, "_element", None)
        if element is not None and any(node.tag in unsupported for node in element.iter()):
            return True
    return False


def render_docx(template: Template, renderer: Renderer) -> tuple[bytes, RenderResult]:
    from docx import Document
    if template.docx_bytes is None:
        document = Document()
        style = document.styles["Normal"]
        from docx.shared import Pt
        style.font.name, style.font.size = "Calibri", Pt(11)
        for line in template.text.split("\n"):
            document.add_paragraph(line)
    else:
        document = Document(io.BytesIO(template.docx_bytes))
        if _unsupported_parts(document):
            raise ValueError("This template has text boxes, tracked changes, or content controls. Accept changes and move report text into ordinary paragraphs, or use text export.")
    aggregate = RenderResult("")
    for paragraph in document_paragraphs(document):
        result = renderer.render(paragraph.text)
        aggregate.edits.extend(result.edits)
        aggregate.warnings.extend(result.warnings)
        aggregate.errors.extend(result.errors)
        apply_paragraph_edits(paragraph, result.edits)
    aggregate.text = body_text(document)
    aggregate.errors = list(dict.fromkeys(aggregate.errors))
    aggregate.warnings = list(dict.fromkeys(aggregate.warnings))
    output = io.BytesIO()
    document.save(output)
    return output.getvalue(), aggregate
