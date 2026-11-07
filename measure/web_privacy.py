"""Memory-only browser imports and session-scoped framework cleanup."""
from io import BytesIO
from pathlib import Path

from measure.documents import Template, body_text
from measure.importers import Table, parse_delimited, _rectangular


def read_template_upload(upload):
    suffix = Path(upload.name).suffix.lower()
    payload = upload.getvalue()
    if suffix == '.docx':
        from docx import Document
        text = body_text(Document(BytesIO(payload)))
        return Template(text, payload, text)
    if suffix in ('.txt', '.md'):
        text = payload.decode('utf-8-sig')
        return Template(text, original_text=text)
    raise ValueError('Upload a Word (.docx), text (.txt), or Markdown (.md) file.')


def read_score_bytes(payload, suffix):
    if suffix == '.csv':
        try:
            text = payload.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = payload.decode('cp1252')
        return [Table('Scores', parse_delimited(text))]
    from openpyxl import load_workbook
    workbook = load_workbook(BytesIO(payload), read_only=True, data_only=True)
    try:
        return [Table(sheet.title, _rectangular(sheet.iter_rows(values_only=True)))
                for sheet in workbook if sheet.max_row]
    finally:
        workbook.close()


def clear_framework_session_files():
    """Release this session's upload and generated-download references on Restart.

    Streamlit manager APIs are internal, so their contract is covered by tests.
    This releases references; it is not secure erasure of RAM or host storage.
    """
    from streamlit import runtime
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    context = get_script_run_ctx()
    if context is None or not runtime.exists():
        return
    instance = runtime.get_instance()
    instance.uploaded_file_mgr.remove_session_files(context.session_id)
    instance.media_file_mgr.clear_session_refs(context.session_id)
    instance.media_file_mgr.remove_orphaned_files()
