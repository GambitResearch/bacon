"""Utilities for string manipulation."""

import re


def bssplit(s, sep, maxsplit=0):
    r"""Similare to ``s.split(sep)``, but avoid \-escaped sep."""
    rv = s.split(sep)
    i = 0
    while i + 1 < len(rv):
        if not rv[i].endswith("\\"):
            i += 1
        else:
            rv[i] = rv[i][:-1] + sep + rv[i + 1]
            del rv[i + 1]

    return rv


def bsescape(s, unsafe):
    """Backslash escape certain characters from a string."""
    # TODO: cache small patterns
    rex = re.compile("[" + re.escape(unsafe + "\\") + "]")
    return rex.sub(lambda m: "\\" + m.group(0), s)


def bsunescape(s, _rex=re.compile(r"\\(.)")):
    """Remove backslash-escaping from a string."""
    return _rex.sub(lambda m: m.group(1), s)


def ensure_unicode(s):
    if isinstance(s, bytes):
        return s.decode("utf-8")
    elif isinstance(s, str):
        return s
    else:
        return str(s)
