"""Name matching aids, not test items, norms, scoring keys, or definitions."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"[^\w]+", " ", text).strip()


@dataclass(frozen=True)
class MeasureName:
    name: str
    kind: str = "standard"
    aliases: tuple[str, ...] = ()


WIAT = [MeasureName(name) for name in (
    "Total Achievement", "Reading", "Written Expression", "Mathematics",
    "Basic Reading", "Decoding", "Reading Fluency", "Math Fluency",
    "Writing Fluency", "Oral Language", "Phonological Processing",
    "Orthographic Processing", "Dyslexia Index", "Word Reading",
    "Reading Comprehension", "Spelling", "Alphabet Writing Fluency",
    "Sentence Composition", "Essay Composition", "Math Problem Solving",
    "Numerical Operations", "Pseudoword Decoding", "Phonemic Proficiency",
    "Oral Reading Fluency", "Orthographic Fluency", "Decoding Fluency",
    "Listening Comprehension", "Oral Expression", "Sentence Writing Fluency",
    "Receptive Vocabulary", "Oral Discourse Comprehension",
    "Expressive Vocabulary", "Oral Word Fluency", "Sentence Repetition",
    "Sentence Building", "Sentence Combining",
)] + [MeasureName(f"Math Fluency–{part}", aliases=(
    f"Math Fluency-{part}", f"Math Fluency {part}", f"Math Fluency: {part}"))
    for part in ("Addition", "Subtraction", "Multiplication")]

WAIS_COMMON = [
    MeasureName("Full Scale IQ", aliases=("FSIQ", "Full Scale Intelligence Quotient")),
    MeasureName("Verbal Comprehension", aliases=("VCI", "Verbal Comprehension Index")),
    MeasureName("Working Memory", aliases=("WMI", "Working Memory Index")),
    MeasureName("Processing Speed", aliases=("PSI", "Processing Speed Index")),
    MeasureName("General Ability", aliases=("GAI", "General Ability Index")),
    MeasureName("Cognitive Proficiency", aliases=("CPI", "Cognitive Proficiency Index")),
] + [MeasureName(name, "scaled") for name in (
    "Similarities", "Vocabulary", "Information", "Comprehension", "Block Design",
    "Visual Puzzles", "Matrix Reasoning", "Figure Weights", "Arithmetic",
    "Coding", "Symbol Search", "Letter-Number Sequencing")]
WAIS5 = WAIS_COMMON + [
    MeasureName("Visual Spatial", aliases=("VSI", "Visual Spatial Index")),
    MeasureName("Fluid Reasoning", aliases=("FRI", "Fluid Reasoning Index")),
    MeasureName("Nonverbal", aliases=("NVI", "Nonverbal Index")),
] + [MeasureName(name, "scaled") for name in (
    "Digit Sequencing", "Running Digits", "Digits Forward", "Digits Backward",
    "Set Relations", "Symbol Span", "Spatial Addition", "Naming Speed Quantity")]
WAIS4 = WAIS_COMMON + [
    MeasureName("Perceptual Reasoning", aliases=("PRI", "Perceptual Reasoning Index")),
] + [MeasureName(name, "scaled") for name in (
    "Digit Span", "Cancellation", "Picture Completion")]

PAI = [MeasureName(name, "t", (code,)) for code, name in (
    ("ICN", "Inconsistency"), ("INF", "Infrequency"),
    ("NIM", "Negative Impression Management"), ("PIM", "Positive Impression Management"),
    ("SOM", "Somatic Complaints"), ("ANX", "Anxiety"),
    ("ARD", "Anxiety-Related Disorders"), ("DEP", "Depression"),
    ("MAN", "Mania"), ("PAR", "Paranoia"), ("SCZ", "Schizophrenia"),
    ("BOR", "Borderline Features"), ("ANT", "Antisocial Features"),
    ("ALC", "Alcohol Problems"), ("DRG", "Drug Problems"),
    ("AGG", "Aggression"), ("SUI", "Suicidal Ideation"), ("STR", "Stress"),
    ("NON", "Nonsupport"), ("RXR", "Treatment Rejection"),
    ("DOM", "Dominance"), ("WRM", "Warmth"),
)] + [MeasureName(code, "t") for code in (
    "SOM-C", "SOM-S", "SOM-H", "ANX-C", "ANX-A", "ANX-P",
    "ARD-O", "ARD-P", "ARD-T", "DEP-C", "DEP-A", "DEP-P",
    "MAN-A", "MAN-G", "MAN-I", "PAR-H", "PAR-P", "PAR-R",
    "SCZ-P", "SCZ-S", "SCZ-T", "BOR-A", "BOR-I", "BOR-N", "BOR-S",
    "ANT-A", "ANT-E", "ANT-S", "AGG-A", "AGG-V", "AGG-P")]

CATALOGS = {"WIAT-4": WIAT, "WAIS-5": WAIS5, "WAIS-IV": WAIS4, "PAI": PAI}
TESTS = tuple(CATALOGS)
SCORE_TYPES = {"standard": "Standard score", "scaled": "Scaled score", "t": "T score"}


def lookup(test: str, name: str) -> MeasureName | None:
    key = normalize(name)
    # The word Index or Composite may be added in score-table headings.
    choices = {key, re.sub(r" (?:composite|index)$", "", key)}
    for item in CATALOGS.get(test, ()):
        if choices.intersection(normalize(x) for x in (item.name, *item.aliases)):
            return item
    return None
