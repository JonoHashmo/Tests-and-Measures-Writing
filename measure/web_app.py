"""Chrome-compatible Streamlit entry point; no Tk or shared case storage."""
from __future__ import annotations

from pathlib import Path
import sys

# Works with `streamlit run measure/web_app.py` from a repository checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from measure.catalog import TESTS, reference_sections
from measure.documents import Template, render_docx
from measure.engine import Renderer, missing_mentions, review
from measure.importers import Table, parse_delimited
from measure.web_profiles import COLUMNS, fixed_scores, profile_for, columns_for
from measure.web_spreadsheets import EXCEL_MIME, excel_template, read_score_upload
from measure.web_privacy import read_template_upload, clear_framework_session_files
from measure.rules import category_for
from measure.strengths import DEFAULT_DEFINITIONS, CODES, strength_text, PRONOUNS, change_pronouns


def score_frame(scores, test):
    columns = columns_for(test)
    frame = pd.DataFrame([{key: score.to_dict()[key] for key in columns} for score in scores], columns=columns)
    frame['score'] = pd.to_numeric(frame['score'], errors='coerce').astype(float)
    return frame


def scores_from_frame(frame, test):
    columns = columns_for(test)
    rows = [columns]
    for row in frame.to_dict('records'):
        values = ['' if pd.isna(row[k]) else str(row[k]) for k in columns]
        if any(values):
            rows.append(values)
    if len(rows) == 1:
        return []
    return fixed_scores(Table('Score editor', rows), test)[0]


def reset_workspace():
    clear_framework_session_files()
    for key in list(st.session_state):
        del st.session_state[key]


def go(step):
    st.session_state.step = step
    st.rerun()


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
    if st.sidebar.button('Restart'):
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
        score_step(test)
    elif step == 2:
        wording_step()
    else:
        review_step(test)


def update_definition_pronouns():
    previous = st.session_state.get('pronouns_mode', 'She / her')
    selected = st.session_state.pronouns_widget
    for code in CODES:
        value = change_pronouns(st.session_state.definitions[code], previous, selected)
        st.session_state.definitions[code] = value
        st.session_state[f'definition_{code}'] = value
    st.session_state.pronouns_mode = selected


def score_step(test):
    st.subheader('2. Import and review scores')
    st.caption('Download the template below or use your own. Make sure to use column names: ' + ', '.join(columns_for(test)) + '.')
    st.download_button('Download Excel score template (.xlsx)', excel_template(test), f'{test}-score-template.xlsx', mime=EXCEL_MIME)
    if test in DEFAULT_DEFINITIONS:
        st.caption('For any measure, enter NS, PS, NW, or PW in strengths. Combine labels with commas, such as NS, PS. Leave blank when not applicable.')
        if 'definitions' not in st.session_state:
            st.session_state.definitions = dict(DEFAULT_DEFINITIONS[test])
        st.radio('Pronouns for strength and weakness definitions', PRONOUNS,
            index=PRONOUNS.index(st.session_state.get('pronouns_mode', 'She / her')),
            key='pronouns_widget', horizontal=True, on_change=update_definition_pronouns)
        with st.expander('Strength and weakness definitions (edit for this report)'):
            st.caption('Edit names and pronouns to fit your report. Changes apply to this session and selected test.')
            for code in CODES:
                key = f'definition_{code}'
                if key not in st.session_state:
                    st.session_state[key] = st.session_state.definitions[code]
                value = st.text_area(code, key=key)
                st.session_state.definitions[code] = value
    with st.expander('Accepted names' if test == 'WIAT-4' else 'Accepted names and abbreviations'):
        for title, measures in reference_sections(test):
            st.markdown(f'**{title}**')
            rows = [{'Name': m.name} if test == 'WIAT-4' else
                    {'Name': m.name, 'Abbreviation': m.aliases[0]} for m in measures]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
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
    st.subheader('Or paste your score table here')
    st.caption('Copy your table from Excel or Numbers, including the column headers. Paste below, then click outside the box to load it automatically.')
    pasted = st.text_area('Paste score table', height=260,
        placeholder='name\tscore\tpercentile\nWord Reading\t92\t30', key='pasted_scores')
    paste_error = False
    if pasted.strip() and pasted != st.session_state.get('last_pasted_scores'):
        try:
            rows, notes = fixed_scores(Table('Pasted table', parse_delimited(pasted)), test)
            st.session_state.scores = rows
            st.session_state.revision += 1
            st.session_state.last_pasted_scores = pasted
            for note in notes:
                st.warning(note)
            st.success(f'Loaded {len(rows)} scores from your pasted table. Review them below.')
        except ValueError as exc:
            paste_error = True
            st.error(f'Cannot read the pasted table: {exc} Your previous scores have not been replaced.')
    if not st.session_state.scores:
        st.button('Continue to wording', disabled=True)
        return
    st.markdown('**Review your scores**')
    edited = st.data_editor(score_frame(st.session_state.scores, test), num_rows='dynamic', hide_index=True,
        key=f'scores_{st.session_state.revision}')
    try:
        scores = scores_from_frame(edited, test)
        score_errors = []
    except ValueError as exc:
        scores, score_errors = [], [str(exc)]
    for error in score_errors:
        st.error(error)
    if test in DEFAULT_DEFINITIONS:
        for row in scores:
            try:
                strength_text(row.strengths, st.session_state.definitions)
            except ValueError as exc:
                score_errors.append(str(exc))
                st.error(str(exc))
    st.session_state.current_scores = scores
    if st.button('Continue to wording', disabled=paste_error or bool(score_errors) or not scores):
        st.session_state.scores = scores
        st.session_state.revision += 1
        go(2)



def wording_step():
    st.subheader('3. Import your wording')
    template_upload = st.file_uploader('Report template', type=['txt', 'md', 'docx'])
    if st.button('Load uploaded template', disabled=template_upload is None):
        try:
            template = read_template_upload(template_upload)
            st.session_state.template = template
            st.session_state.wording = template.text
            st.session_state.editor_wording = template.text
        except Exception as exc:
            st.error(f'Cannot load template: {exc}')
    st.subheader('Or paste your report wording here')
    st.caption('Paste or type your report text below. If you uploaded a file, click Load uploaded template to show its text here. You can edit it in this box.')
    text = st.text_area('Report wording', key='editor_wording', value=st.session_state.wording, height=280,
        placeholder='Paste your report wording here, or upload a template above.',
        help='Paste text directly from Word or another editor. Example: Word Reading was in the XX range (SS = XX, XX%ile).')
    st.session_state.wording = text
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    if original.docx_bytes and template is not original:
        st.caption('Edited Word text will export with standard formatting. Reload the original to retain its formatting.')
    st.caption('To report scores, end the sentence with (SS = XX, XX%ile). The app replaces that marker; mentions without a marker are left alone. For several measures in one sentence, name the result: (Mathematics: SS = XX, XX%ile). Strength/weakness explanations follow the score parentheses as separate sentences, with each code defined only on its first use.')
    if st.button('Continue to review', disabled=not text.strip()):
        go(3)


def review_step(test):
    scores = st.session_state.scores
    text = st.session_state.wording
    original = st.session_state.template
    template = original if original.docx_bytes and text == original.original_text else Template(text)
    options = dict(auto_insert=True, include_percentile=True,
                   include_ci=False, first_only=False, policy='rules', report_style='narrative',
                   strength_definitions=st.session_state.get('definitions', {}), marker_only=True)
    st.subheader('4. Review and download')
    errors, notes = review(test, scores, st.session_state.rules, 'rules')
    if not scores:
        errors.append('Import or enter at least one score.')
    if not text.strip():
        errors.append('Import or enter report wording.')
    for error in errors:
        st.error(error)
    for note in notes:
        if not note.endswith(': no category; enter a label or add a cutoff rule.'):
            st.warning(note)
    missing_categories = [row.name for row in scores
        if not errors and not category_for(row, st.session_state.rules, 'rules', test)[0]]
    if missing_categories:
        st.info('Descriptive labels are unavailable for: ' + ', '.join(missing_categories) +
            '. The app has not been set up with score ranges for these measures or scores. '
            'This does not mean your scores are incorrect. Their scores can still be inserted, '
            'but labels such as “Average” will not be added automatically. '
            'You can download the report if it does not explicitly request these missing labels; '
            'review and add the appropriate descriptions in Word if needed.')
    if errors:
        return
    renderer = lambda: Renderer(test, scores, st.session_state.rules, **options)
    result = renderer().render(text)
    for note in result.warnings:
        st.warning(note)
    for error in result.errors:
        st.error(report_error(error))
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
                st.error(report_error(error))
        else:
            for warning in word_result.warnings:
                st.warning(warning)
            st.download_button('Download Word document (.docx)', word, 'Measure-report.docx',
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except Exception as exc:
        st.error(f'Word export unavailable: {exc}')


def report_error(message):
    suffix = ': category is missing; fill it in or remove that placeholder.'
    if message.endswith(suffix):
        name = message[:-len(suffix)]
        return (f'{name}: no descriptive category is configured for this measure or score. '
                'Your score has not been changed. Ask the app owner to supply the category definitions, '
                'or go back to Report wording and remove the request for a category '
                '(for example, “in the XX range”) while keeping the score marker. '
                'The report can be downloaded once no missing category is requested.')
    return message


if __name__ == '__main__':
    main()
