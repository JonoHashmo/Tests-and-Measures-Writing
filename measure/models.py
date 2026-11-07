from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re

from .catalog import SCORE_TYPES, normalize


@dataclass
class Score:
    name: str
    score: float | None
    score_type: str = "standard"
    percentile: str = ""
    ci: str = ""
    category: str = ""
    aliases: list[str] = field(default_factory=list)
    age_eq: str = ""
    grade_eq: str = ""
    raw_score: str = ""
    source: str = "Manual entry"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Score":
        valid = set(cls.__dataclass_fields__)
        if not isinstance(data, dict) or set(data) - valid:
            raise ValueError("Invalid score record in project.")
        return cls(**data)

    def validate(self) -> list[str]:
        problems = []
        for attr in ("name", "score_type", "percentile", "ci", "category", "age_eq", "grade_eq", "raw_score", "source"):
            if not isinstance(getattr(self, attr), str):
                problems.append(f"Score field {attr} must be text.")
        if problems:
            return problems
        if not isinstance(self.name, str) or not self.name.strip():
            problems.append("A score row has no name.")
        if self.score_type not in SCORE_TYPES:
            problems.append(f"{self.name}: choose a valid score type.")
        if not isinstance(self.aliases, list) or not all(isinstance(a, str) for a in self.aliases):
            problems.append(f"{self.name}: aliases must be a list of names.")
        if self.score is None:
            problems.append(f"{self.name}: score is missing.")
        elif isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(self.score):
            problems.append(f"{self.name}: score must be a finite number.")
        elif self.score_type == "scaled" and not 1 <= self.score <= 19:
            problems.append(f"{self.name}: scaled score is outside 1–19; check the score type.")
        elif self.score_type == "standard" and not 1 <= self.score <= 250:
            problems.append(f"{self.name}: standard score is outside the supported range 1–250.")
        elif self.score_type == "t" and not 0 <= self.score <= 150:
            problems.append(f"{self.name}: T score is outside the supported range 0–150.")
        if self.score is not None and isinstance(self.score, (int, float)) and math.isfinite(self.score):
            if self.score != int(self.score):
                problems.append(f"{self.name}: scores must be whole numbers.")
        if self.percentile:
            value = re.fullmatch(r"\s*[<>≤≥]?\s*(\d+(?:\.\d+)?)\s*%?\s*", str(self.percentile))
            if not value or not 0 <= float(value.group(1)) <= 100:
                problems.append(f"{self.name}: percentile must be 0–100 (optional < or >).")
        if self.ci:
            ci = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*", str(self.ci))
            if not ci:
                problems.append(f"{self.name}: confidence interval must look like 87–97.")
            elif float(ci.group(1)) > float(ci.group(2)):
                problems.append(f"{self.name}: confidence interval bounds are reversed.")
            elif self.score is not None and isinstance(self.score, (int, float)) and not float(ci.group(1)) <= self.score <= float(ci.group(2)):
                problems.append(f"{self.name}: confidence interval does not contain the score.")
        return problems


def number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if float(value).is_integer() else str(value)


def validate_scores(scores: list[Score]) -> list[str]:
    issues, seen = [], set()
    for row in scores:
        issues.extend(row.validate())
        key = normalize(row.name)
        if key in seen:
            issues.append(f"{row.name}: duplicate row; keep one score per measure.")
        seen.add(key)
    return issues
