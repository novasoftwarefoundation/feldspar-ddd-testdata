"""Serialize JSON the way Google Takeout writes it. Two styles occur in one archive:

- "gson":  '[{' / '},{' joins for lists of objects, inline lists of scalars, indent 2;
- "plain": standard indent 2, but lists of scalars inline.
Both with or without Gson's HTML-safe escapes (= ' & < > as \\u00XX).
``pick(raw)`` returns the (style, escape) that reproduces the original bytes, or None.
"""
import json

GSON_ESC = {"=": "\\u003d", "'": "\\u0027", "&": "\\u0026", "<": "\\u003c", ">": "\\u003e"}


def _s(x, esc):
    out = json.dumps(x, ensure_ascii=False)
    if esc and isinstance(x, str):
        for k, v in GSON_ESC.items():
            out = out.replace(k, v)
    return out


def dumps(o, style, esc, ind=0):
    pad = "  " * ind
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = [pad + "  " + _s(k, esc) + ": " + dumps(v, style, esc, ind + 1) for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(o, list):
        if not o:
            return "[]"
        if all(isinstance(x, dict) for x in o):
            if style == "gson":
                return "[" + ",".join(dumps(x, style, esc, ind) for x in o) + "]"
            return "[\n" + ",\n".join(pad + "  " + dumps(x, style, esc, ind + 1) for x in o) + "\n" + pad + "]"
        return "[" + ", ".join(_s(x, esc) for x in o) + "]"
    return _s(o, esc)


def pick(raw: bytes):
    data = json.loads(raw)
    for style in ("gson", "plain"):
        for esc in (True, False):
            if dumps(data, style, esc).encode("utf-8") == raw:
                return style, esc
    return None
