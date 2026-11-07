"""Owner-maintained test settings, separate from the user-facing workflow."""
import json
from pathlib import Path

from measure.catalog import lookup
from measure.importers import ImportProblem, Table, scores_from_table
from measure.rules import validate_rules

COLUMNS = ['name', 'score', 'percentile']


def profile_for(test):
    profile = json.loads(Path(__file__).with_name('test_profiles.json').read_text())[test]
    errors = validate_rules(profile['rules'], test)
    if errors:
        raise ValueError('\n'.join(errors))
    return profile


def fixed_scores(table, test):
    from measure.strengths import parse_strengths
    from measure.catalog import normalize
    headings = [str(v).strip().lower() for v in table.rows[0]] if table.rows else []
    if headings not in (COLUMNS, COLUMNS + ['strengths']):
        raise ImportProblem('Use name, score, percentile, and an optional strengths column, in that order. Download the Excel template for the correct layout.')
    has_strengths = 'strengths' in headings
    usable_rows = [COLUMNS]
    strengths = {}
    for i, original in enumerate(table.rows[1:], 2):
        if len(original) != len(headings):
            raise ImportProblem(f'Row {i}: expected {len(headings)} columns.')
        row = original[:3]
        value = str(original[3]).strip() if has_strengths else ''
        if not any(str(v).strip() for v in row) and not value:
            usable_rows.append(['', '', ''])
            continue
        if str(row[0]).strip() and not str(row[1]).strip() and not str(row[2]).strip() and not value:
            usable_rows.append(['', '', ''])
            continue
        if not str(row[0]).strip() or not str(row[1]).strip():
            raise ImportProblem(f'Row {i}: name and score are required. Percentile and strengths may be blank.')
        known = lookup(test, str(row[0]))
        if known is None:
            raise ImportProblem(f'Row {i}: {row[0]!r} is not a recognized name for {test}. Use a name from the reference table.')
        codes = parse_strengths(value)
        if codes and (test == 'PAI' or known.kind != 'standard'):
            raise ImportProblem(f'{known.name}: strengths are supported only for WIAT composites and WAIS indexes, not subtests or PAI scales.')
        if codes and test == 'WIAT-4' and known.name not in WIAT_COMPOSITES:
            raise ImportProblem(f'{known.name}: strengths are supported only for composites, not WIAT subtests.')
        key = normalize(known.name)
        labels = ', '.join(codes)
        if key in strengths and strengths[key] != labels:
            raise ImportProblem(f'{known.name}: duplicate rows have different strengths. Keep one row per measure.')
        strengths[key] = labels
        usable_rows.append(row)
    if not any(row[0] for row in usable_rows[1:]):
        raise ImportProblem('Enter a score for at least one measure. You can leave every other measure blank.')
    scores, notes = scores_from_table(Table(table.title, usable_rows), dict(zip(COLUMNS, range(3))), test)
    for score in scores:
        score.strengths = strengths[normalize(score.name)]
    return scores, notes


WIAT_COMPOSITES = frozenset((
    'Total Achievement', 'Reading', 'Written Expression', 'Mathematics',
    'Basic Reading', 'Decoding', 'Reading Fluency', 'Math Fluency', 'Writing Fluency',
    'Oral Language', 'Phonological Processing', 'Orthographic Processing', 'Dyslexia Index',
))


def columns_for(test):
    return COLUMNS if test == 'PAI' else COLUMNS + ['strengths']
