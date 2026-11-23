"""A small YAML reader and writer for the files this repository writes itself.

Supports block mappings, block sequences and scalars. Strings are written as
JSON-style double-quoted scalars, which YAML reads the same way, so no
third-party package is needed. Keys are written in sorted order.
"""
import json
import re


def _scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return json.dumps(str(value), ensure_ascii=False)


def _key(key):
    key = str(key)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) and key not in ("true", "false", "null"):
        return key
    return _scalar(key)


def _emit(value, indent, lines):
    pad = "  " * indent
    if isinstance(value, dict):
        for key in sorted(value):
            item = value[key]
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{_key(key)}:")
                _emit(item, indent + 1, lines)
            else:
                lines.append(f"{pad}{_key(key)}: {_empty(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item:
                sub = []
                _emit(item, indent + 1, sub)
                sub[0] = pad + "- " + sub[0][len(pad) + 2:]
                lines.extend(sub)
            elif isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}-")
                _emit(item, indent + 1, lines)
            else:
                lines.append(f"{pad}- {_empty(item)}")


def _empty(item):
    if isinstance(item, dict):
        return "{}"
    if isinstance(item, list):
        return "[]"
    return _scalar(item)


def dumps(value, header=""):
    lines = [f"# {line}".rstrip() for line in header.splitlines()]
    _emit(value, 0, lines)
    return "\n".join(lines) + "\n"


def _parse_scalar(text):
    text = text.strip()
    if text == "{}":
        return {}
    if text == "[]":
        return []
    if text in ("null", "~", ""):
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    try:
        return json.loads(text)
    except ValueError:
        return text


def _split_key(text):
    """Split 'key: value' where key may be a double-quoted string."""
    if text.startswith('"'):
        decoder = json.JSONDecoder()
        key, end = decoder.raw_decode(text)
        rest = text[end:].lstrip()
        assert rest.startswith(":"), text
        return key, rest[1:].strip()
    key, _, rest = text.partition(":")
    return key.strip(), rest.strip()


def loads(text):
    rows = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rows.append((len(raw) - len(raw.lstrip(" ")), stripped))
    value, _ = _block(rows, 0, rows[0][0] if rows else 0)
    return value if value is not None else {}


def _block(rows, i, indent):
    if i >= len(rows):
        return None, i
    if rows[i][1].startswith("- ") or rows[i][1] == "-":
        result = []
        while i < len(rows) and rows[i][0] == indent and (rows[i][1].startswith("- ") or rows[i][1] == "-"):
            body = rows[i][1][1:].strip()
            if not body:
                item, i = _block(rows, i + 1, rows[i + 1][0])
                result.append(item)
                continue
            if _is_mapping_line(body):
                # A mapping that starts on the dash line: re-indent it as a block.
                child_indent = indent + 2
                sub = [(child_indent, body)]
                j = i + 1
                while j < len(rows) and rows[j][0] > indent:
                    sub.append(rows[j])
                    j += 1
                item, _ = _block(sub, 0, child_indent)
                result.append(item)
                i = j
            else:
                result.append(_parse_scalar(body))
                i += 1
        return result, i
    result = {}
    while i < len(rows) and rows[i][0] == indent:
        key, rest = _split_key(rows[i][1])
        if rest:
            result[key] = _parse_scalar(rest)
            i += 1
        elif i + 1 < len(rows) and rows[i + 1][0] > indent:
            result[key], i = _block(rows, i + 1, rows[i + 1][0])
        else:
            result[key] = None
            i += 1
    return result, i


def _is_mapping_line(body):
    if body.startswith('"'):
        try:
            _split_key(body)
            return True
        except (AssertionError, ValueError):
            return False
    return ":" in body and not body.startswith("{")
