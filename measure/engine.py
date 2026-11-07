"""Auditable score insertion. No generative model or remote service is used."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import re

from .catalog import CATALOGS, lookup, normalize
from .models import Score, number, validate_scores
from .rules import category_for, computed_category, validate_rules


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str
    measure: str
    reason: str


@dataclass
class RenderResult:
    text: str
    edits: list[Edit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


TOKEN = re.compile(r"\{\{\s*(.+?)\s*\}\}", re.DOTALL)
ATTRIBUTES = {"score", "percentile", "percentile_report", "score_summary", "strengths", "ci", "category", "name", "summary", "age_eq", "grade_eq", "raw_score", "score_type"}
LABELS = {"standard": "SS", "scaled": "Scaled score", "t": "T"}


def percentile_report(value: str) -> str:
    """Ordinal ranks; decimals retain their value without an invented suffix."""
    if not value:
        return ''
    match = re.fullmatch(r'\s*([<>≤≥]?)\s*(\d+(?:\.\d+)?)\s*%?\s*', value)
    if not match:
        return ''
    sign, digits = match.groups()
    rank = float(digits)
    if rank.is_integer():
        n = int(rank)
        suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f'{sign}{n}{suffix}%ile'
    return f'{sign}{digits}%ile'


def _name_pattern(name: str) -> str:
    # Dash/space differences in publisher exports should not require edits.
    chunks = re.split(r"([\s\-–—:]+)", name.strip())
    body = "".join(r"[\s\-–—:]+" if re.fullmatch(r"[\s\-–—:]+", chunk) else re.escape(chunk) for chunk in chunks)
    is_code = bool(re.fullmatch(r"[A-Z][A-Z0-9-]{1,7}", name))
    return body if is_code else f"(?i:{body})"


class Renderer:
    def __init__(self, test: str, scores: list[Score], rules: dict,
                 policy: str = "imported", auto_insert: bool = True,
                 include_percentile: bool = True, include_ci: bool = False,
                 first_only: bool = False, report_style: str = 'legacy', strength_definitions: dict | None = None,
                 marker_only: bool = False, subject_name: str = 'XXX'):
        self.marker_only = marker_only
        self.subject_name = subject_name.strip() or 'XXX'
        self.defined_strengths = set()
        from .strengths import DEFAULT_DEFINITIONS, strength_text
        self.strength_definitions = dict(DEFAULT_DEFINITIONS.get(test, {}) if strength_definitions is None else strength_definitions)
        self.report_style = report_style
        self.test, self.scores, self.rules = test, scores, rules
        self.policy, self.auto_insert = policy, auto_insert
        self.include_percentile, self.include_ci, self.first_only = include_percentile, include_ci, first_only
        self.aliases: dict[str, Score] = {}
        self.names: list[str] = []
        self.errors = validate_scores(scores) + validate_rules(rules, test)
        for row in scores:
            if row.strengths:
                try:
                    strength_text(row.strengths, self.strength_definitions)
                except ValueError as exc:
                    self.errors.append(f'{row.name}: {exc}')
        for row in scores:
            known = lookup(test, row.name)
            names = [row.name, *row.aliases]
            if known:
                names += [known.name, *known.aliases]
            for name in names:
                if not name.strip():
                    continue
                key = normalize(name)
                if key in self.aliases and self.aliases[key] is not row:
                    self.errors.append(f"Ambiguous name {name!r} belongs to more than one score row.")
                self.aliases[key] = row
                self.names.append(name)
        alternatives = sorted(set(self.names), key=len, reverse=True)
        self.pattern = re.compile(r"(?<![\w-])(?:" + "|".join(_name_pattern(n) for n in alternatives) + r")(?![\w-])") if alternatives else None
        self.used: set[str] = set()

    def category(self, row: Score) -> str:
        return category_for(row, self.rules, self.policy, self.test)[0]

    def summary(self, row: Score, include_category: bool = True, include_strengths: bool = True) -> str:
        bits = [f"{LABELS[row.score_type]} = {number(row.score)}"]
        if self.include_percentile and row.percentile:
            bits.append(percentile_report(row.percentile) if self.report_style == 'narrative' else f"PR = {row.percentile}")
        if self.include_ci and row.ci:
            bits.append(f"CI = {row.ci}")
        if include_category and self.category(row):
            bits.append(self.category(row))
        return (", " if self.report_style == 'narrative' else "; ").join(bits)

    def strength_sentence(self, row):
        from .strengths import parse_strengths
        parts = []
        for code in parse_strengths(row.strengths):
            label = self.strength_definitions[code].strip().rstrip(',. ')
            if code in self.defined_strengths:
                parts.append(f'This was also a {code} for {self.subject_name}.')
            else:
                parts.append(f'This was also a {label}.')
                self.defined_strengths.add(code)
        return ' '.join(parts)

    def marker_edits(self, text, result, token_ranges):
        # Parentheses may contain the nested abbreviation in Standard Score (SS).
        parentheses = re.compile(r'\((?:[^()\n]|\(SS\))*\)', re.I)
        blank_score = re.compile(r'\b(?:SS|T|Scaled score|Standard Score(?:\s*\(SS\))?)\s*=\s*(?:X+S?|_+|\?+)(?!\w)', re.I)
        all_names = [(name, item) for item in CATALOGS[self.test] for name in (item.name, *item.aliases)]
        all_names.sort(key=lambda pair: len(pair[0]), reverse=True)
        for marker in parentheses.finditer(text):
            if not blank_score.search(marker.group()):
                continue
            if any(start < marker.end() and end > marker.start() for start, end in token_ranges):
                continue
            # A marker must be the last item in its sentence or paragraph.
            if not re.match(r'\s*(?:[.!?]|\n|$)', text[marker.end():]):
                result.errors.append('Move the blank score parentheses to the end of the sentence so the app can safely insert the result.')
                continue
            boundaries = list(re.finditer(r'[.!?](?:\s+|$)|\n', text[:marker.start()]))
            left = boundaries[-1].end() if boundaries else 0
            sentence = text[left:marker.start()]
            explicit = marker.group()[1:].split(':', 1)[0].strip() if ':' in marker.group() else ''
            known = lookup(self.test, explicit) if explicit else None
            if explicit and known is None:
                result.errors.append(f'{explicit}: the name inside the score marker is not recognized. Use an accepted measure name or abbreviation.')
                continue
            if known is None:
                occupied, found = [], {}
                for name, item in all_names:
                    for match in re.finditer(r'(?<![\w-])' + _name_pattern(name) + r'(?![\w-])', sentence):
                        if any(a <= match.start() < b for a, b in occupied):
                            continue
                        occupied.append(match.span())
                        found[item.name] = item
                if len(found) == 1:
                    known = next(iter(found.values()))
            if known is None:
                result.errors.append('A blank score marker has no single matching measure. Name it inside the parentheses, for example (Mathematics: SS = XX, XX%ile).')
                continue
            row = self.aliases.get(normalize(known.name))
            if row is None:
                result.errors.append(f'{known.name}: this sentence requests scores, but none were supplied. Add its score or remove the blank score parentheses.')
                continue
            if self.include_percentile and re.search(r'%ile|percentile', marker.group(), re.I) and not row.percentile:
                result.errors.append(f'{row.name}: the score marker requests a percentile, but the table has none. Add it or remove the percentile from the marker.')
                continue
            category = re.search(r'\bin the\s+([\w -]+?)\s+range\b', sentence, re.I)
            if category:
                if not self.category(row):
                    result.errors.append(f'{row.name}: category is missing; fill it in or remove that placeholder.')
                    continue
                a, b = category.span(1)
                if not any(e.start < left + b and e.end > left + a for e in result.edits):
                    result.edits.append(Edit(left+a, left+b, self.category(row), row.name, 'Category in sentence'))
            prefix = f'{explicit}: ' if explicit else ''
            category_token = any(left <= e.start < marker.start() and e.measure == row.name and
                                 e.reason == 'Placeholder: category' for e in result.edits)
            replacement = f'({prefix}{self.summary(row, include_category=not bool(category or category_token))})'
            end = marker.end()
            tail = text[end:]
            punctuation = re.match(r'[ \t]*([.!?])', tail)
            if row.strengths:
                if punctuation:
                    replacement += punctuation.group(1)
                    end += punctuation.end()
                else:
                    replacement += '.'
                replacement += f' \x00strengths:{row.name}\x00'
            result.edits.append(Edit(marker.start(), end, replacement, row.name, 'Score marker'))

    def field(self, row: Score, attr: str) -> str:
        if attr == "summary":
            return self.summary(row)
        if attr == "score_summary":
            return self.summary(row, include_category=False, include_strengths=False)
        if attr == "strengths":
            return self.strength_sentence(row)
        if attr == "percentile_report":
            return percentile_report(row.percentile)
        if attr == "category":
            return self.category(row)
        if attr == "score":
            return number(row.score)
        if attr == "score_type":
            return LABELS[row.score_type]
        return str(getattr(row, attr))

    def render(self, text: str) -> RenderResult:
        result = RenderResult(text, errors=list(dict.fromkeys(self.errors)))
        if self.errors:
            return result
        token_ranges = []
        token_measures = set()
        for match in TOKEN.finditer(text):
            token_ranges.append(match.span())
            content = match.group(1).strip()
            if "." in content:
                name, attr = content.rsplit(".", 1)
                name, attr = name.strip(), attr.strip().lower()
            else:
                name, attr = content, "summary"
            row = self.aliases.get(normalize(name))
            if not row:
                result.errors.append(f"No score row matches {{{{{content}}}}}.")
            elif attr not in ATTRIBUTES:
                result.errors.append(f"Unknown placeholder field {attr!r} in {{{{{content}}}}}.")
            else:
                replacement = (f'\x00strengths:{row.name}\x00' if row.strengths else '') if attr == 'strengths' else self.field(row, attr)
                if not replacement:
                    result.errors.append(f"{row.name}: {attr} is missing; fill it in or remove that placeholder.")
                else:
                    end = match.end() + (1 if attr == 'strengths' and text[match.end():match.end()+1] == '.' else 0)
                    result.edits.append(Edit(match.start(), end, replacement, row.name, f"Placeholder: {attr}"))
                    token_measures.add(normalize(row.name))
        # Unclosed tokens are never exported as if they were completed.
        uncovered = TOKEN.sub("", text)
        if "{{" in uncovered or "}}" in uncovered:
            result.errors.append("A placeholder has unmatched braces. Use {{Measure.field}}.")
        if self.auto_insert and self.marker_only:
            self.marker_edits(text, result, token_ranges)
        if self.auto_insert and self.pattern and not self.marker_only:
            annotated_sentences = set()
            for match in self.pattern.finditer(text):
                if any(start <= match.start() < end for start, end in token_ranges):
                    continue
                row = self.aliases.get(normalize(match.group()))
                if row is None:
                    continue
                # If a sentence uses a placeholder for this measure, it is already explicit.
                left = max(text.rfind("\n", 0, match.start()), text.rfind(". ", 0, match.start())) + 1
                candidates = [x for x in (text.find("\n", match.end()), text.find(". ", match.end())) if x >= 0]
                right = min(candidates, default=len(text))
                if (left, right) in annotated_sentences:
                    continue
                explicit_here = any(left <= edit.start < right and edit.measure == row.name for edit in result.edits if edit.reason.startswith("Placeholder"))
                if explicit_here:
                    continue
                key = normalize(row.name)
                if self.first_only and key in self.used:
                    continue
                if self.report_style == 'narrative':
                    sentence = text[left:right]
                    # Only move a score to a sentence end when its measure is unambiguous.
                    mentions = {normalize(self.aliases[normalize(m.group())].name)
                                for m in self.pattern.finditer(sentence)}
                    if len(mentions) == 1:
                        category = re.search(r'\bin the\s+([\w -]+?)\s+range\b', sentence, re.I)
                        if category and self.category(row):
                            if re.search(r'\b(?:SS|T|Scaled score)\s*=\s*\d', sentence, re.I):
                                result.warnings.append(f'{row.name}: existing score annotation retained; verify it against the table.')
                                continue
                            start, end = category.span(1)
                            result.edits.append(Edit(left + start, left + end, self.category(row), row.name, 'Category in sentence'))
                            insertion = right
                            while insertion > left and text[insertion - 1].isspace():
                                insertion -= 1
                            if insertion > left and text[insertion - 1] in '.!?':
                                insertion -= 1
                            result.edits.append(Edit(insertion, insertion, f' ({self.summary(row, include_category=False)})', row.name, 'Name match'))
                            annotated_sentences.add((left, right))
                            self.used.add(key)
                            continue
                tail = text[match.end():match.end() + 140]
                if re.match(r"\s*\((?:SS|T|PR|CI|Scaled score|standard score)\s*(?:=|:)" , tail, re.I):
                    result.warnings.append(f"{row.name}: existing score annotation retained; verify it against the table.")
                    continue
                key = normalize(row.name)
                if self.first_only and key in self.used:
                    continue
                annotation = f" ({self.summary(row)})"
                result.edits.append(Edit(match.end(), match.end(), annotation, row.name, "Name match"))
                self.used.add(key)
        result.edits.sort(key=lambda edit: (edit.start, edit.end))
        # Resolve first-use definitions in document order, shared across Word paragraphs.
        result.edits = [replace(edit, replacement=re.sub(r'\x00strengths:([^\x00]+)\x00',
            lambda m: self.strength_sentence(self.aliases[normalize(m.group(1))]), edit.replacement))
            for edit in result.edits]
        assembled, cursor = [], 0
        for edit in result.edits:
            assembled += [text[cursor:edit.start], edit.replacement]
            cursor = edit.end
        assembled.append(text[cursor:])
        result.text = "".join(assembled)
        result.warnings = list(dict.fromkeys(result.warnings))
        return result


def review(test: str, scores: list[Score], config: dict, policy: str) -> tuple[list[str], list[str]]:
    errors = validate_scores(scores) + validate_rules(config, test)
    warnings = []
    if errors:
        return errors, warnings
    for row in scores:
        calculated = computed_category(row, config, test)
        if row.category and calculated and normalize(row.category) != normalize(calculated):
            chosen = row.category if policy == "imported" else calculated
            warnings.append(f"{row.name}: entered label '{row.category}', rule label '{calculated}'; using '{chosen}'.")
        if not category_for(row, config, policy, test)[0]:
            warnings.append(f"{row.name}: no category; enter a label or add a cutoff rule.")
    return errors, warnings


def missing_mentions(test: str, text: str, scores: list[Score]) -> list[str]:
    """Surface likely unfilled measures; never infer a missing numeric value."""
    present = {normalize(row.name) for row in scores}
    found = []
    # Longest names first avoids flagging Reading inside Word Reading.
    names = [(n, item) for item in CATALOGS.get(test, ()) for n in (item.name, *item.aliases)]
    names.sort(key=lambda pair: len(pair[0]), reverse=True)
    occupied = []
    for name, item in names:
        for match in re.finditer(r"(?<![\w-])" + _name_pattern(name) + r"(?![\w-])", text):
            if any(s <= match.start() < e for s, e in occupied):
                continue
            occupied.append(match.span())
            if normalize(item.name) not in present:
                found.append(item.name)
    return list(dict.fromkeys(found))
