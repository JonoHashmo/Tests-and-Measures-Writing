"""User-entered strength/weakness labels; never inferred from score cutoffs."""
import re

CODES = ('NS', 'PS', 'NW', 'PW')
DEFAULT_DEFINITIONS = {
    'PAI': {
        'NS': 'Normative Strength (NS)',
        'PS': 'Personal Strength (PS)',
        'NW': 'Normative Weakness (NW)',
        'PW': 'Personal Weakness (PW)',
    },
    'WIAT-4': {
        'NS': 'Normative Strength (NS), meaning her performance was higher than that of average peers her age',
        'PS': 'Personal Strength (PS), meaning she performed better on this composite than on composites measuring other abilities',
        'NW': 'Normative Weakness (NW), meaning her performance was much lower than that of average peers her age',
        'PW': 'Personal Weakness (PW), meaning her performance was much lower when compared to her average overall achievement',
    },
    'WAIS-5': {
        'NS': 'Normative Strength (NS), meaning her performance was higher than that of her average peers',
        'PS': 'Personal Strength (PS), meaning she performed better on this Index than on Indexes measuring other abilities',
        'NW': 'Normative Weakness (NW), meaning her performance was much lower than that of her average peers',
        'PW': 'Personal Weakness (PW), meaning her performance was much lower than on other measures of her ability',
    },
}


def parse_strengths(value):
    if not isinstance(value, str):
        raise ValueError('Strengths must be text: NS, PS, NW, or PW, separated by commas.')
    codes = list(dict.fromkeys(c for c in re.split(r'[,;/\s]+', value.strip().upper()) if c))
    if any(c not in CODES for c in codes):
        raise ValueError('Use only NS, PS, NW, or PW in strengths, separated by commas (for example: NS, PS).')
    if {'NS', 'NW'} <= set(codes) or {'PS', 'PW'} <= set(codes):
        raise ValueError('A measure cannot be both NS and NW, or both PS and PW. Check its strengths column.')
    return codes


def strength_text(value, definitions):
    codes = parse_strengths(value)
    missing = [code for code in codes if not definitions.get(code, '').strip()]
    if missing:
        raise ValueError('Enter a definition for ' + ', '.join(missing) + ' in Strength and weakness definitions.')
    return '; '.join(definitions[code].strip() for code in codes)
