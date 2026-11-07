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
    if not table.rows or [str(v).strip().lower() for v in table.rows[0]] != COLUMNS:
        raise ImportProblem('Use exactly these three column headers, in order: name, score, percentile. Download the score table template below.')
    for i, row in enumerate(table.rows[1:], 2):
        if len(row) != 3:
            raise ImportProblem(f'Row {i}: expected exactly three columns.')
        if not any(str(v).strip() for v in row):
            continue
        if not str(row[0]).strip() or not str(row[1]).strip():
            raise ImportProblem(f'Row {i}: name and score are required. Percentile may be blank.')
        if lookup(test, str(row[0])) is None:
            raise ImportProblem(f'Row {i}: {row[0]!r} is not a recognized name for {test}. Use a name from the reference table.')
    return scores_from_table(table, dict(zip(COLUMNS, range(3))), test)
