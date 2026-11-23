"""Serialize JSON the way Meta's export writes it (indent 2, ASCII escapes, empty lists as '[\\n  \\n]')."""
import json

def dumps(o, ind=0):
    pad = "  " * ind
    if isinstance(o, dict):
        if not o:
            return "{\n" + pad + "  \n" + pad + "}"
        items = [pad + "  " + json.dumps(k) + ": " + dumps(v, ind + 1) for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(o, list):
        if not o:
            return "[\n" + pad + "  \n" + pad + "]"
        return "[\n" + ",\n".join(pad + "  " + dumps(v, ind + 1) for v in o) + "\n" + pad + "]"
    return json.dumps(o)
