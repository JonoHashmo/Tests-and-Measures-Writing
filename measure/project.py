"""Portable, explicit JSON sessions. No auto-save of assessment data."""
from __future__ import annotations
import base64
import json
from pathlib import Path

from .catalog import TESTS
from .documents import Template
from .models import Score, validate_scores
from .rules import defaults, validate_rules


def save_project(path: str | Path, test: str, scores: list[Score], template: Template,
                 rules: dict, options: dict) -> None:
    payload = {
        "format": "measure-project", "version": 1, "test": test,
        "scores": [row.to_dict() for row in scores], "template": template.text,
        "docx": base64.b64encode(template.docx_bytes).decode("ascii") if template.docx_bytes else None,
        "rules": rules, "options": options,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str, list[Score], Template, dict, dict]:
    if Path(path).stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Project exceeds 50 MB. Use a smaller Word template.")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != "measure-project" or payload.get("version") != 1:
        raise ValueError("This is not a supported Measure project.")
    test = payload.get("test")
    if test not in TESTS:
        raise ValueError("The project uses an unsupported assessment.")
    scores = [Score.from_dict(row) for row in payload.get("scores", [])]
    rules = payload.get("rules", defaults(test))
    errors = validate_scores(scores) + validate_rules(rules, test)
    if errors:
        raise ValueError("\n".join(errors))
    text = payload.get("template", "")
    if not isinstance(text, str):
        raise ValueError("Project template must be text.")
    docx = base64.b64decode(payload["docx"], validate=True) if payload.get("docx") else None
    options = payload.get("options", {})
    if not isinstance(options, dict) or any(type(options.get(k, True)) is not bool for k in ("auto_insert", "include_percentile", "include_ci", "first_only")):
        raise ValueError("Invalid project report options.")
    if options.get("policy", "imported") not in ("imported", "rules"):
        raise ValueError("Invalid classification policy.")
    return test, scores, Template(text, docx, text), rules, options
