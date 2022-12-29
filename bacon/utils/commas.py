"""
Recipe 498181: Add thousands separator commas to formatted numbers (Python)

http://code.activestate.com/recipes/498181/ (r1)

"""

import re

try:
    xrange
except NameError:
    xrange = range

__test__ = {}

re_digits_nondigits = re.compile(r"\d+|\D+")

__test__[
    "re_digits_nondigits"
] = r"""

	>>> re_digits_nondigits.findall('$1234.1234')
	['$', '1234', '.', '1234']
	>>> re_digits_nondigits.findall('1234')
	['1234']
	>>> re_digits_nondigits.findall('')
	[]

"""


def FormatWithCommas(format, value):
    """

    >>> FormatWithCommas('%.4f', .1234)
    '0.1234'
    >>> FormatWithCommas('%i', 100)
    '100'
    >>> FormatWithCommas('%.4f', 234.5678)
    '234.5678'
    >>> FormatWithCommas('$%.4f', 234.5678)
    '$234.5678'
    >>> FormatWithCommas('%i', 1000)
    '1,000'
    >>> FormatWithCommas('%.4f', 1234.5678)
    '1,234.5678'
    >>> FormatWithCommas('$%.4f', 1234.5678)
    '$1,234.5678'
    >>> FormatWithCommas('%i', 1000000)
    '1,000,000'
    >>> FormatWithCommas('%.4f', 1234567.5678)
    '1,234,567.5678'
    >>> FormatWithCommas('$%.4f', 1234567.5678)
    '$1,234,567.5678'
    >>> FormatWithCommas('%i', -100)
    '-100'
    >>> FormatWithCommas('%.4f', -234.5678)
    '-234.5678'
    >>> FormatWithCommas('$%.4f', -234.5678)
    '$-234.5678'
    >>> FormatWithCommas('%i', -1000)
    '-1,000'
    >>> FormatWithCommas('%.4f', -1234.5678)
    '-1,234.5678'
    >>> FormatWithCommas('$%.4f', -1234.5678)
    '$-1,234.5678'
    >>> FormatWithCommas('%i', -1000000)
    '-1,000,000'
    >>> FormatWithCommas('%.4f', -1234567.5678)
    '-1,234,567.5678'
    >>> FormatWithCommas('$%.4f', -1234567.5678)
    '$-1,234,567.5678'

    """

    parts = re_digits_nondigits.findall(format % (value,))
    for i in xrange(len(parts)):
        s = parts[i]
        if s.isdigit():
            parts[i] = _commafy(s)
            break
    return "".join(parts)


def _commafy(s):
    r = []
    append = r.append
    for i, c in enumerate(reversed(s)):
        if i and (not (i % 3)):
            append(",")
        append(c)
    r.reverse()
    return "".join(r)
