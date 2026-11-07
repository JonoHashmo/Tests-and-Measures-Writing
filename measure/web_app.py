"""Chrome-compatible Streamlit entry point; no Tk or shared case storage."""
from __future__ import annotations

from copy import deepcopy
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

# Works with `streamlit run measure/web_app.py` from a repository checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from measure.catalog import TESTS
from measure.documents import Template, load_template, render_docx
from measure.engine import Renderer, missing_mentions, review
from measure.importers import FIELDS, guess_header, header_mapping, read_tables, scores_from_table
from measure.models import Score
from measure.rules import defaults, validate_rules

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
COLUMNS = ['name', 'score', 'score_type', 'percentile', 'ci', 'category', 'aliases', 'age_eq', 'grade_eq', 'raw_score']


def uploaded_file(upload, reader):
    """Existing path-based readers get an isolated, short-lived file."""
    with TemporaryDirectory(prefix='measure-upload-') as directory:
        path = Path(directory) / ('upload' + Path(upload.name).suffix.lower())
        path.write_bytes(upload.getvalue())
        return reader(path)


def score_frame(scores):
    records = []
    for score in scores:
        row = score.to_dict()
        row['aliases'] = '; '.join(score.aliases)
        records.append({key: row[key] for key in COLUMNS})
    frame = pd.DataFrame(records, columns=COLUMNS)
    frame['score'] = pd.to_numeric(frame['score'], errors='coerce').astype(float)
    return frame


def scores_from_frame(frame):
    result = []
    for row in frame.to_dict('records'):
        row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        if not any(v is not None and str(v).strip() for v in row.values()):
            continue
        score = row.pop('score')
        aliases = row.pop('aliases') or ''
        row = {key: str(value) if value is not None else '' for key, value in row.items()}
        result.append(Score(**row, score=score, aliases=[a.strip() for a in aliases.split(';') if a.strip()]))
    return result


def reset_workspace():
    for key in list(st.session_state):
        if key != 'assessment':
            del st.session_state[key]


def main():
    st.set_page_config(page_title='Measure | Report workspace', page_icon='📄', layout='wide')
    st.title('Measure')
    st.caption('Your report, with less repetition. Import scores, keep your wording, download the report.')
    st.info('Online testing: use fictional data. Hosted uploads are processed on the hosting server. '
            'This app adds no case database or shared cache. Download your work before closing your session.')
    test = st.sidebar.selectbox('Assessment', TESTS, key='assessment', on_change=reset_workspace)
    if st.sidebar.button('Clear session'):
        reset_workspace()
        st.rerun()
    if 'scores' not in st.session_state:
        st.session_state.scores = []
        st.session_state.rules = defaults(test)
        st.session_state.template = Template('')
        st.session_state.wording = ''
        st.session_state.revision = 0
    if st.sidebar.button('Try fictional example'):
        stem = {'WIAT-4': 'WIAT4', 'WAIS-5': 'WAIS5', 'WAIS-IV': 'WAIS5', 'PAI': 'PAI'}[test]
        if test == 'WAIS-IV':
            st.sidebar.caption('This workflow example uses shared WAIS measure names, not edition-specific norms.')
        table = read_tables(EXAMPLES / f'{stem}_scores.csv')[0]
        st.session_state.scores, _ = scores_from_table(table, header_mapping(table.rows[0]), test)
        template = load_template(EXAMPLES / f'{stem}_template.txt')
        st.session_state.template = template
        st.session_state.wording = template.text
        st.session_state.revision += 1
    st.sidebar.caption('Already-scored results only. No raw-score conversion or clinical interpretation.')

    st.subheader('1. Import and review scores')
    upload = st.file_uploader('Score table', type=['csv', 'tsv', 'xlsx', 'docx', 'pdf', 'txt'])
    if upload:
        try:
            tables = uploaded_file(upload, read_tables)
            if not tables:
                raise ValueError('No readable tables found. Try CSV or Excel instead.')
            index = st.selectbox('Table or sheet', range(len(tables)), format_func=lambda i: tables[i].title)
            table = tables[index]
            if not table.rows:
                raise ValueError('The selected table is empty.')
            header = st.number_input('Header row (first row is 1)', min_value=1, max_value=len(table.rows), value=guess_header(table.rows) + 1)
            headings = table.rows[header - 1]
            st.dataframe(pd.DataFrame(table.rows[header:header + 5]), hide_index=True)
            guessed = header_mapping(headings)
            mapping = {}
            with st.expander('Map columns', expanded=True):
                for field, label in FIELDS.items():
                    choices = [None] + list(range(len(headings)))
                    mapping[field] = st.selectbox(label, choices, index=choices.index(guessed.get(field)),
                        format_func=lambda i: 'Not imported' if i is None else f'{i + 1}: {headings[i]}', key=f'map_{field}')
            if st.button('Import table (replaces current scores)'):
                rows, notes = scores_from_table(table, {k: v for k, v in mapping.items() if v is not None}, test, header - 1)
                st.session_state.scores = rows
                st.session_state.revision += 1
                for note in notes:
                    st.warning(note)
                st.success(f'Imported {len(rows)} scores.')
        except Exception as exc:
            st.error(f'Cannot import table: {exc}')
    edited = st.data_editor(score_frame(st.session_state.scores), num_rows='dynamic', hide_index=True,
        key=f'scores_{st.session_state.revision}',
        column_config={'score_type': st.column_config.SelectboxColumn('Score type', options=['standard', 'scaled', 't']),
                       'aliases': st.column_config.TextColumn('Aliases (separate with ;)')})
    scores = scores_from_frame(edited)

    st.subheader('2. Set descriptive ranges')
    policy = st.radio('Category source', ['imported', 'rules'], horizontal=True,
        format_func=lambda x: 'Imported labels, then rules' if x == 'imported' else 'Cutoff rules only')
    if test == 'PAI':
        st.caption('PAI requires named scale rules or imported labels. No blanket T-score classification is applied.')
    config = deepcopy(st.session_state.rules)
    with st.expander('Edit cutoff ranges'):
        group = st.selectbox('Rule group', ['standard', 'scaled'] if test != 'PAI' else ['Named scale'])
        name = st.text_input('Named scale/subtest override (optional)' if test != 'PAI' else 'Scale name or code (e.g. ANX)')
        bands = config['overrides'].get(name.strip(), []) if name.strip() else (config[group] if group != 'Named scale' else [])
        ranges = st.data_editor(pd.DataFrame(bands, columns=['min', 'max', 'label']), num_rows='dynamic', hide_index=True,
            key=f'ranges_{test}_{group}_{name}', column_config={
                'min': st.column_config.NumberColumn('Minimum', step=1),
                'max': st.column_config.NumberColumn('Maximum', step=1)})
        if st.button('Apply cutoff ranges'):
            try:
                parsed = []
                for row in ranges.to_dict('records'):
                    lo, hi = float(row['min']), float(row['max'])
                    if not lo.is_integer() or not hi.is_integer():
                        raise ValueError('Cutoff endpoints must be whole numbers.')
                    parsed.append({'min': int(lo), 'max': int(hi), 'label': str(row['label'] or '')})
                if name.strip():
                    config['overrides'][name.strip()] = parsed
                elif group == 'Named scale':
                    raise ValueError('Enter a scale name first.')
                else:
                    config[group] = parsed
                problems = validate_rules(config, test)
                if problems:
                    raise ValueError('\n'.join(problems))
                st.session_state.rules = config
                st.success('Cutoff rules applied.')
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
                config = deepcopy(st.session_state.rules)

    st.subheader('3. Import your wording')
    template_upload = st.file_uploader('Report template', type=['txt', 'md', 'docx'])
    if st.button('Load uploaded template', disabled=template_upload is None):
        try:
            template = uploaded_file(template_upload, load_template)
            st.session_state.template = template
            st.session_state.wording = template.text
        except Exception as exc:
            st.error(f'Cannot load template: {exc}')
    text = st.text_area('Report wording', key='wording', height=280,
        help='Example: Word Reading was {{Word Reading.category}} (SS = {{Word Reading.score}}).')
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    if original.docx_bytes and template is not original:
        st.caption('Edited Word text will export with standard formatting. Reload the original to retain its formatting.')
    auto = st.checkbox('Insert scores after matching measure names', value=True)
    pr = st.checkbox('Include percentile ranks', value=True)
    ci = st.checkbox('Include confidence intervals', value=False)
    first = st.checkbox('Annotate only the first mention', value=False)
    options = dict(auto_insert=auto, include_percentile=pr, include_ci=ci, first_only=first, policy=policy)

    st.subheader('4. Review and download')
    errors, notes = review(test, scores, st.session_state.rules, policy)
    if not scores:
        errors.append('Import or enter at least one score.')
    if not text.strip():
        errors.append('Import or enter report wording.')
    for error in errors:
        st.error(error)
    for note in notes:
        st.warning(note)
    if errors:
        return
    renderer = lambda: Renderer(test, scores, st.session_state.rules, **options)
    result = renderer().render(text)
    for note in result.warnings:
        st.warning(note)
    for name in missing_mentions(test, text, scores):
        st.warning(f'{name}: mentioned in the template but has no imported score.')
    for error in result.errors:
        st.error(error)
    st.text_area('Report preview', value=result.text, height=300, disabled=True)
    if result.errors:
        return
    st.download_button('Download text report', result.text, 'Measure-report.txt', mime='text/plain')
    try:
        word, word_result = render_docx(template, renderer())
        if word_result.errors:
            for error in word_result.errors:
                st.error(error)
        else:
            for warning in word_result.warnings:
                st.warning(warning)
            st.download_button('Download Word report', word, 'Measure-report.docx',
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except Exception as exc:
        st.error(f'Word export unavailable: {exc}')


if __name__ == '__main__':
    main()
