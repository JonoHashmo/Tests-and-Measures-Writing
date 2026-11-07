"""Chrome-compatible Streamlit entry point; no Tk or shared case storage."""
from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

# Works with `streamlit run measure/web_app.py` from a repository checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from measure.catalog import TESTS, CATALOGS
from measure.documents import Template, load_template, render_docx
from measure.engine import Renderer, missing_mentions, review
from measure.importers import Table, read_tables
from measure.web_profiles import COLUMNS, fixed_scores, profile_for

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def uploaded_file(upload, reader):
    """Existing path-based readers get an isolated, short-lived file."""
    with TemporaryDirectory(prefix='measure-upload-') as directory:
        path = Path(directory) / ('upload' + Path(upload.name).suffix.lower())
        path.write_bytes(upload.getvalue())
        return reader(path)


def score_frame(scores):
    frame = pd.DataFrame([{key: score.to_dict()[key] for key in COLUMNS} for score in scores], columns=COLUMNS)
    frame['score'] = pd.to_numeric(frame['score'], errors='coerce').astype(float)
    return frame


def scores_from_frame(frame, test):
    rows = [COLUMNS]
    for row in frame.to_dict('records'):
        values = ['' if pd.isna(row[k]) else str(row[k]) for k in COLUMNS]
        if any(values):
            rows.append(values)
    if len(rows) == 1:
        return []
    return fixed_scores(Table('Score editor', rows), test)[0]


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
    profile = profile_for(test)
    st.session_state.rules = profile['rules']
    st.sidebar.caption(profile['status'])
    if 'scores' not in st.session_state:
        st.session_state.scores = []
        st.session_state.template = Template('')
        st.session_state.wording = ''
        st.session_state.revision = 0
    if st.sidebar.button('Try fictional example'):
        stem = {'WIAT-4': 'WIAT4', 'WAIS-5': 'WAIS5', 'WAIS-IV': 'WAIS5', 'PAI': 'PAI'}[test]
        if test == 'WAIS-IV':
            st.sidebar.caption('This workflow example uses shared WAIS measure names, not edition-specific norms.')
        table = read_tables(EXAMPLES / f'{stem}_scores.csv')[0]
        st.session_state.scores, _ = fixed_scores(table, test)
        template = load_template(EXAMPLES / f'{stem}_template.txt')
        st.session_state.template = template
        st.session_state.wording = template.text
        st.session_state.revision += 1
    st.sidebar.caption('Already-scored results only. No raw-score conversion or clinical interpretation.')

    st.subheader('1. Import and review scores')
    st.caption('Use exactly three columns: name, score, percentile. Fill in the template and delete unused measure rows. Name and score are required; percentile may be blank.')
    reference = pd.DataFrame([{'name': m.name, 'abbreviations / matching names': '; '.join(m.aliases)} for m in CATALOGS[test]])
    blank = pd.DataFrame({'name': [m.name for m in CATALOGS[test]], 'score': [''] * len(CATALOGS[test]), 'percentile': [''] * len(CATALOGS[test])})
    st.download_button('Download score table template (.csv)', blank.to_csv(index=False), f'{test}-score-template.csv', mime='text/csv')
    with st.expander('Accepted names and abbreviations'):
        st.dataframe(reference, hide_index=True)
    upload = st.file_uploader('Score table', type=['csv', 'xlsx'])
    if upload:
        try:
            tables = uploaded_file(upload, read_tables)
            if not tables:
                raise ValueError('No readable tables found.')
            index = st.selectbox('Table or sheet', range(len(tables)), format_func=lambda i: tables[i].title)
            table = tables[index]
            st.dataframe(pd.DataFrame(table.rows[1:], columns=table.rows[0]), hide_index=True)
            if st.button('Import table (replaces current scores)'):
                rows, notes = fixed_scores(table, test)
                st.session_state.scores = rows
                st.session_state.revision += 1
                for note in notes:
                    st.warning(note)
                st.success(f'Imported {len(rows)} scores.')
        except Exception as exc:
            st.error(f'Cannot import table: {exc}')
    edited = st.data_editor(score_frame(st.session_state.scores), num_rows='dynamic', hide_index=True,
        key=f'scores_{st.session_state.revision}')
    try:
        scores = scores_from_frame(edited, test)
        score_errors = []
    except ValueError as exc:
        scores, score_errors = [], [str(exc)]

    st.subheader('2. Import your wording')
    template_upload = st.file_uploader('Report template', type=['txt', 'md', 'docx'])
    if st.button('Load uploaded template', disabled=template_upload is None):
        try:
            template = uploaded_file(template_upload, load_template)
            st.session_state.template = template
            st.session_state.wording = template.text
        except Exception as exc:
            st.error(f'Cannot load template: {exc}')
    st.caption('Your uploaded text appears below after you click Load uploaded template. You can edit it here. Word formatting is retained on export when this text is unchanged.')
    text = st.text_area('Report wording', key='wording', height=280,
        help='Example: Word Reading was {{Word Reading.category}} (SS = {{Word Reading.score}}).')
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    if original.docx_bytes and template is not original:
        st.caption('Edited Word text will export with standard formatting. Reload the original to retain its formatting.')
    auto = st.checkbox('Insert scores after matching measure names', value=True)
    pr = st.checkbox('Include percentile ranks', value=True)
    options = dict(auto_insert=auto, include_percentile=pr, include_ci=False, first_only=False, policy='rules')

    st.subheader('3. Review and download')
    errors, notes = review(test, scores, st.session_state.rules, 'rules')
    errors.extend(score_errors)
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
    st.caption('Word (.docx) is an editable document with formatting. Plain text (.txt) contains the same report wording without formatting.')
    st.download_button('Download plain text (.txt)', result.text, 'Measure-report.txt', mime='text/plain')
    try:
        word, word_result = render_docx(template, renderer())
        if word_result.errors:
            for error in word_result.errors:
                st.error(error)
        else:
            for warning in word_result.warnings:
                st.warning(warning)
            st.download_button('Download Word document (.docx)', word, 'Measure-report.docx',
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except Exception as exc:
        st.error(f'Word export unavailable: {exc}')


if __name__ == '__main__':
    main()
