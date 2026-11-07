"""User-entered strength/weakness labels; never inferred from score cutoffs."""
import re

CODES = ('NS', 'PS', 'NW', 'PW')
PRONOUNS = ('She / her', 'He / him', 'They / them')


def change_pronouns(text, previous, selected):
    forms = {
        'She / her': ('she', 'her', 'her', 'hers', 'herself'),
        'He / him': ('he', 'him', 'his', 'his', 'himself'),
        'They / them': ('they', 'them', 'their', 'theirs', 'themself'),
    }
    source, target = forms[previous], forms[selected]
    # In these definitions "her"/"his" before a noun is possessive.
    mapping = dict(zip(source, target))
    mapping[source[2]] = target[2]
    def substitute(match):
        word = mapping[match.group().lower()]
        return word.capitalize() if match.group()[0].isupper() else word
    text = re.sub(r'\b(?:' + '|'.join(mapping) + r')\b', substitute, text, flags=re.I)
    if selected == 'They / them':
        for old, new in (('was', 'were'), ('is', 'are'), ('has', 'have'), ('does', 'do')):
            text = re.sub(r'\b(they)\s+' + old + r'\b', lambda m: m.group(1) + ' ' + new, text, flags=re.I)
    elif previous == 'They / them':
        for old, new in (('were', 'was'), ('are', 'is'), ('have', 'has'), ('do', 'does')):
            text = re.sub(r'\b(' + target[0] + r')\s+' + old + r'\b', lambda m: m.group(1) + ' ' + new, text, flags=re.I)
    return text


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
