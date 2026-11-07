"""Excel templates and explicit, non-destructive upload validation."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from measure.catalog import CATALOGS
from measure.importers import read_tables
from measure.web_profiles import columns_for

EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def excel_template(test):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Scores'
    sheet.append(columns_for(test))
    for measure in CATALOGS[test]:
        sheet.append([measure.name] + [None] * (len(columns_for(test)) - 1))
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    sheet.column_dimensions['A'].width = 42
    sheet.column_dimensions['B'].width = 15
    sheet.column_dimensions['C'].width = 18
    sheet.column_dimensions['D'].width = 24
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='245F58')
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def read_score_upload(upload):
    suffix = Path(upload.name).suffix.lower()
    if suffix == '.numbers':
        raise ValueError('Apple Numbers files cannot be imported directly. In Numbers, choose File → Export To → Excel, then upload the exported .xlsx file. Do not rename the file extension.')
    if suffix not in ('.xlsx', '.csv'):
        raise ValueError('Unsupported file type. Upload an Excel (.xlsx) workbook or CSV (.csv). In Numbers, choose File → Export To → Excel first.')
    try:
        with TemporaryDirectory(prefix='measure-scores-') as directory:
            path = Path(directory) / ('scores' + suffix)
            path.write_bytes(upload.getvalue())
            tables = read_tables(path)
        if not tables or not any(table.rows for table in tables):
            raise ValueError('The file contains no readable score tables.')
        return tables
    except Exception as exc:
        raise ValueError('Cannot read this file. It may be damaged, password-protected, or saved in another format. Export a fresh Excel (.xlsx) workbook or CSV; changing the extension does not convert it.') from exc
