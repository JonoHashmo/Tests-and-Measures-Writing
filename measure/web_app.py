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
from measure.importers import Table, read_tables, parse_delimited
from measure.web_profiles import COLUMNS, fixed_scores, profile_for
from measure.web_spreadsheets import EXCEL_MIME, excel_template, read_score_upload

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
        del st.session_state[key]


def go(step):
    st.session_state.step = step
    st.rerun()


def load_example(test):
    stem = {'WIAT-4': 'WIAT4', 'WAIS-5': 'WAIS5', 'PAI': 'PAI'}[test]
    table = read_tables(EXAMPLES / f'{stem}_scores.csv')[0]
    st.session_state.scores, _ = fixed_scores(table, test)
    template = load_template(EXAMPLES / f'{stem}_template.txt')
    st.session_state.template = template
    st.session_state.wording = template.text
    st.session_state.revision += 1


def main():
    st.set_page_config(page_title='Measure | Report workspace', page_icon='📄', layout='wide')
    st.markdown('''<style>
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            font-size: 1.05rem;
            line-height: 1.6;
            color: var(--text-color);
            opacity: 1;
        }
    </style>''', unsafe_allow_html=True)
    if 'step' not in st.session_state:
        st.session_state.update(step=0, active_test=None, scores=[], current_scores=[],
            template=Template(''), wording='', auto=True, pr=True, revision=0)
    step = st.session_state.step
    labels = ['Select test', 'Score table', 'Report wording', 'Review and download']
    st.sidebar.title('Measure')
    for index, label in enumerate(labels):
        st.sidebar.markdown(f"**→ {index + 1}. {label}**" if index == step else f"{index + 1}. {label}")
    if step > 0:
        st.sidebar.caption(st.session_state.active_test)
        if st.sidebar.button('Back a step'):
            if step == 1:
                st.session_state.scores = st.session_state.current_scores
                st.session_state.revision += 1
            go(step - 1)
    if st.sidebar.button('Clear session'):
        reset_workspace()
        st.rerun()
    if step == 0:
        st.title('Which test are you working on?')
        previous = st.session_state.active_test
        selected = st.selectbox('Assessment', TESTS, index=TESTS.index(previous) if previous else None,
            placeholder='Select a test', key='test_choice')
        if st.button('Continue', disabled=selected is None):
            if selected != previous:
                reset_workspace()
                st.session_state.update(step=1, active_test=selected, scores=[], current_scores=[],
                    template=Template(''), wording='', auto=True, pr=True, revision=0)
            else:
                st.session_state.step = 1
            st.rerun()
        return
    test = st.session_state.active_test
    profile = profile_for(test)
    st.session_state.rules = profile['rules']
    st.title(test)
    st.caption("Don't forget to download your report at the end!")
    if step == 1:
        if st.button('Try fictional example'):
            load_example(test)
        score_step(test)
    elif step == 2:
        wording_step()
    else:
        review_step(test)


def score_step(test):
    st.subheader('2. Import and review scores')
    st.caption('Use exactly three columns: name, score, percentile. Fill in the template and delete unused measure rows. Name and score are required; percentile may be blank.')
    reference = pd.DataFrame([{'name': m.name, 'abbreviations / matching names': '; '.join(m.aliases)} for m in CATALOGS[test]])
    st.download_button('Download Excel score template (.xlsx)', excel_template(test), f'{test}-score-template.xlsx', mime=EXCEL_MIME)
    with st.expander('Accepted names and abbreviations'):
        st.dataframe(reference, hide_index=True)
    upload = st.file_uploader('Score table', help='Excel (.xlsx) or CSV. Numbers files must first be exported to Excel.')
    if upload:
        try:
            tables = read_score_upload(upload)
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
    with st.expander('Or paste a score table'):
        st.caption('Copy the three columns, including name, score, percentile headers, from Excel or Numbers and paste below. CSV text also works.')
        pasted = st.text_area('Paste score table', height=180,
            placeholder='name\tscore\tpercentile\nWord Reading\t92\t30', key='pasted_scores')
        if st.button('Import pasted table (replaces current scores)', disabled=not pasted.strip()):
            try:
                rows, notes = fixed_scores(Table('Pasted table', parse_delimited(pasted)), test)
                st.session_state.scores = rows
                st.session_state.revision += 1
                for note in notes:
                    st.warning(note)
                st.success(f'Imported {len(rows)} scores from pasted table.')
            except ValueError as exc:
                st.error(f'Cannot import pasted table: {exc}')
    edited = st.data_editor(score_frame(st.session_state.scores), num_rows='dynamic', hide_index=True,
        key=f'scores_{st.session_state.revision}')
    try:
        scores = scores_from_frame(edited, test)
        score_errors = []
    except ValueError as exc:
        scores, score_errors = [], [str(exc)]
    for error in score_errors:
        st.error(error)
    st.session_state.current_scores = scores
    if st.button('Continue to wording', disabled=bool(score_errors) or not scores):
        st.session_state.scores = scores
        st.session_state.revision += 1
        go(2)



def wording_step():
    st.subheader('3. Import your wording')
    template_upload = st.file_uploader('Report template', type=['txt', 'md', 'docx'])
    if st.button('Load uploaded template', disabled=template_upload is None):
        try:
            template = uploaded_file(template_upload, load_template)
            st.session_state.template = template
            st.session_state.wording = template.text
            st.session_state.editor_wording = template.text
        except Exception as exc:
            st.error(f'Cannot load template: {exc}')
    st.caption('Upload a file above, or simply paste/type your report text in the box below. Uploaded text appears here after you click Load uploaded template. You can edit it here. Pasted text uses standard document formatting; unedited Word uploads retain their supported formatting.')
    text = st.text_area('Report wording', key='editor_wording', value=st.session_state.wording, height=280,
        placeholder='Paste your report wording here, or upload a template above.',
        help='Paste text directly from Word or another editor. Example: Word Reading was {{Word Reading.category}} (SS = {{Word Reading.score}}).')
    st.session_state.wording = text
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    if original.docx_bytes and template is not original:
        st.caption('Edited Word text will export with standard formatting. Reload the original to retain its formatting.')
    auto = st.checkbox('Insert scores after matching measure names', value=st.session_state.auto)
    pr = st.checkbox('Include percentile ranks', value=st.session_state.pr)
    st.session_state.auto, st.session_state.pr = auto, pr
    if st.button('Continue to review', disabled=not text.strip()):
        go(3)


def review_step(test):
    scores = st.session_state.scores
    text = st.session_state.wording
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    options = dict(auto_insert=st.session_state.auto, include_percentile=st.session_state.pr,
                   include_ci=False, first_only=False, policy='rules')
    st.subheader('4. Review and download')
    errors, notes = review(test, scores, st.session_state.rules, 'rules')
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
    st.success("DONE! 🎉 The boilerplate parts of your report are ready! Don't forget to add context-specific interpretations at the end of each paragraph. 🙂")
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
