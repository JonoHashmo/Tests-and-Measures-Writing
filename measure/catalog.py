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

WAIS_INDEXES = (
    MeasureName("Full Scale IQ", aliases=("FSIQ", "Full Scale Intelligence Quotient")),
    MeasureName("Verbal Comprehension", aliases=("VCI", "Verbal Comprehension Index")),
    MeasureName("Working Memory", aliases=("WMI", "Working Memory Index")),
    MeasureName("Processing Speed", aliases=("PSI", "Processing Speed Index")),
    MeasureName("General Ability", aliases=("GAI", "General Ability Index")),
    MeasureName("Cognitive Proficiency", aliases=("CPI", "Cognitive Proficiency Index")),
    MeasureName("Visual Spatial", aliases=("VSI", "Visual Spatial Index")),
    MeasureName("Fluid Reasoning", aliases=("FRI", "Fluid Reasoning Index")),
    MeasureName("Nonverbal", aliases=("NVI", "Nonverbal Index")),
)
WAIS_SUBTESTS = tuple(MeasureName(name, "scaled", (code,)) for name, code in (
    ("Similarities", "SI"), ("Vocabulary", "VC"), ("Information", "IN"),
    ("Comprehension", "CO"), ("Block Design", "BD"), ("Visual Puzzles", "VP"),
    ("Matrix Reasoning", "MR"), ("Figure Weights", "FW"), ("Arithmetic", "AR"),
    ("Set Relations", "SR"), ("Digit Sequencing", "DQ"), ("Running Digits", "RD"),
    ("Digits Forward", "DF"), ("Digits Backward", "DB"),
    ("Letter-Number Sequencing", "LN"), ("Symbol Span", "SSP"),
    ("Spatial Addition", "SA"), ("Coding", "CD"), ("Symbol Search", "SS"),
    ("Naming Speed Quantity", "NSQ"),
))
WAIS5 = WAIS_INDEXES + WAIS_SUBTESTS

# Fixed presentation order also governs the downloadable score template.
PAI_GROUPS = (
    ("Validity scales", (("Inconsistency", "ICN"), ("Infrequency", "INF"),
        ("Negative Impression", "NIM"), ("Positive Impression", "PIM"))),
    ("Clinical scales", (("Somatic Complaints", "SOM"), ("Anxiety", "ANX"),
        ("Anxiety-Related Disorders", "ARD"), ("Depression", "DEP"),
        ("Mania", "MAN"), ("Paranoia", "PAR"), ("Schizophrenia", "SCZ"),
        ("Borderline Features", "BOR"), ("Antisocial Features", "ANT"),
        ("Alcohol Problems", "ALC"), ("Drug Problems", "DRG"))),
    ("Treatment consideration scales", (("Aggression", "AGG"),
        ("Suicidal Ideation", "SUI"), ("Stress", "STR"), ("Nonsupport", "NON"),
        ("Treatment Rejection", "RXR"))),
    ("Interpersonal scales", (("Dominance", "DOM"), ("Warmth", "WRM"))),
)
PAI_SUBSCALES = {
    "SOM": (("Conversion", "C"), ("Somatization", "S"), ("Health Concerns", "H")),
    "ANX": (("Cognitive", "C"), ("Affective", "A"), ("Physiological", "P")),
    "ARD": (("Obsessive-Compulsive", "O"), ("Phobias", "P"), ("Traumatic Stress", "T")),
    "DEP": (("Cognitive", "C"), ("Affective", "A"), ("Physiological", "P")),
    "MAN": (("Activity Level", "A"), ("Grandiosity", "G"), ("Irritability", "I")),
    "PAR": (("Hypervigilance", "H"), ("Persecution", "P"), ("Resentment", "R")),
    "SCZ": (("Psychotic Experiences", "P"), ("Social Detachment", "S"), ("Thought Disorder", "T")),
    "BOR": (("Affective Instability", "A"), ("Identity Problems", "I"),
        ("Negative Relationships", "N"), ("Self-Harm", "S")),
    "ANT": (("Antisocial Behaviors", "A"), ("Egocentricity", "E"), ("Stimulus-Seeking", "S")),
    "AGG": (("Aggressive Attitude", "A"), ("Verbal Aggression", "V"), ("Physical Aggression", "P")),
}


def _pai_measures(parents):
    result = []
    for name, code in parents:
        legacy = (name + " Management",) if code in ("NIM", "PIM") else ()
        result.append(MeasureName(name, "t", (code, *legacy)))
        for subscale, suffix in PAI_SUBSCALES.get(code, ()):
            result.append(MeasureName(f"{name}-{subscale}", "t", (f"{code}-{suffix}",)))
    return tuple(result)


PAI = tuple(measure for _, parents in PAI_GROUPS for measure in _pai_measures(parents))
CATALOGS = {"WIAT-4": tuple(WIAT), "WAIS-5": WAIS5, "PAI": PAI}


def reference_sections(test):
    """Stable, test-specific names and display abbreviations for every user."""
    if test == "WIAT-4":
        return (("Composites and subtests", CATALOGS[test]),)
    if test == "WAIS-5":
        return (("Composites and indexes", WAIS_INDEXES), ("Subtests", WAIS_SUBTESTS))
    return tuple((title, _pai_measures(parents)) for title, parents in PAI_GROUPS)


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
