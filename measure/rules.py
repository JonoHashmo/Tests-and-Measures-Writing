"""Explicit, editable reporting conventions. Never convert raw scores to norms."""
from __future__ import annotations

from copy import deepcopy
from .catalog import normalize
from .models import Score


STANDARD = [
    {"min": 1, "max": 69, "label": "Extremely low"},
    {"min": 70, "max": 79, "label": "Very low"},
    {"min": 80, "max": 89, "label": "Low average"},
    {"min": 90, "max": 109, "label": "Average"},
    {"min": 110, "max": 119, "label": "High average"},
    {"min": 120, "max": 129, "label": "Very high"},
    {"min": 130, "max": 250, "label": "Extremely high"},
]
# An editable local reporting convention, not an official publisher scale.
SCALED = [
    {"min": 1, "max": 3, "label": "Extremely low"},
    {"min": 4, "max": 5, "label": "Very low"},
    {"min": 6, "max": 7, "label": "Below average"},
    {"min": 8, "max": 12, "label": "Average"},
    {"min": 13, "max": 14, "label": "Above average"},
    {"min": 15, "max": 16, "label": "Very high"},
    {"min": 17, "max": 19, "label": "Extremely high"},
]


def defaults(test: str) -> dict:
    if test == "WIAT-4":
        return {"standard": deepcopy(STANDARD), "scaled": [], "t": [], "overrides": {}}
    if test.startswith("WAIS"):
        return {"standard": deepcopy(STANDARD), "scaled": deepcopy(SCALED), "t": [], "overrides": {}}
    # PAI rules are deliberately scale-specific. No blanket clinical threshold.
    return {"standard": [], "scaled": [], "t": [], "overrides": {}}


def validate_rules(config: dict, test: str) -> list[str]:
    issues = []
    if not isinstance(config, dict) or set(config) != {"standard", "scaled", "t", "overrides"}:
        return ["Rules must contain standard, scaled, t, and overrides."]
    if not isinstance(config["overrides"], dict):
        return ["Rules overrides must be an object keyed by scale or subtest name."]
    groups = [(key, config[key]) for key in ("standard", "scaled", "t")]
    groups += list(config["overrides"].items())
    if test == "PAI" and any(config[k] for k in ("standard", "scaled", "t")):
        issues.append("PAI categories must use a named scale override, not a blanket cutoff.")
    for group, bands in groups:
        if not isinstance(bands, list):
            issues.append(f"{group}: bands must be a list.")
            continue
        checked = []
        for band in bands:
            if not isinstance(band, dict) or set(band) != {"min", "max", "label"}:
                issues.append(f"{group}: every band needs min, max, and label.")
                continue
            lo, hi, label = band["min"], band["max"], band["label"]
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (lo, hi)) or lo > hi:
                issues.append(f"{group}: min/max must be whole numbers, min ≤ max.")
            elif not isinstance(label, str) or not label.strip():
                issues.append(f"{group}: each band needs a category label.")
            else:
                checked.append((lo, hi))
        checked.sort()
        for left, right in zip(checked, checked[1:]):
            if right[0] <= left[1]:
                issues.append(f"{group}: cutoff bands overlap at {right[0]}.")
    keys = [normalize(k) for k in config["overrides"]]
    if len(set(keys)) != len(keys):
        issues.append("Two override names refer to the same measure.")
    return issues


def computed_category(row: Score, config: dict, test: str = "") -> str:
    from .catalog import lookup
    names = {normalize(row.name), *(normalize(a) for a in row.aliases)}
    known = lookup(test, row.name)
    if known:
        names.update(normalize(a) for a in (known.name, *known.aliases))
    override = [(key, value) for key, value in config.get("overrides", {}).items() if normalize(key) in names]
    if len(override) > 1:
        raise ValueError(f"{row.name}: multiple cutoff overrides match this measure.")
    bands = override[0][1] if override else config.get(row.score_type, [])
    if row.score is not None:
        for band in bands:
            if band["min"] <= row.score <= band["max"]:
                return band["label"]
    return ""


def category_for(row: Score, config: dict, policy: str = "imported", test: str = "") -> tuple[str, str]:
    calculated = computed_category(row, config, test)
    if policy == "imported" and row.category.strip():
        return row.category.strip(), "Imported / entered label"
    if calculated:
        return calculated, "Cutoff rule"
    if policy == "imported" and row.category.strip():
        return row.category.strip(), "Imported / entered label"
    return "", "No category rule"
