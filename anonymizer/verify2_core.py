"""Shared helpers: leaf strings of a Meta-style JSON export, and pairwise original/copy leaves."""
import json
import re


def fix(s):
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _walk(n, path, out):
    if isinstance(n, dict):
        for k, v in n.items():
            if k == "string_map_data" and isinstance(v, dict):
                for mk, mv in v.items():
                    _walk(mv, path + ".smd:" + fix(mk), out)
            elif isinstance(n.get("label"), str) and k in ("value", "href", "vec"):
                _walk(v, path + ".label:" + fix(n["label"]) + "." + k, out)
            else:
                _walk(v, path + "." + k, out)
    elif isinstance(n, list):
        for x in n:
            _walk(x, path, out)
    elif isinstance(n, str):
        out.append((path, fix(n)))


def leaves(z):
    out = []
    for i in z.infolist():
        if i.filename.endswith(".json"):
            tmp = []
            _walk(json.loads(z.read(i)), i.filename.rsplit("/", 1)[-1], tmp)
            out += [(i.filename, f, v) for f, v in tmp]
    return out


def pairs(orig, copy):
    out = []
    for a, b in zip(orig.infolist(), copy.infolist()):
        if a.filename.endswith(".json"):
            ta, tb = [], []
            _walk(json.loads(orig.read(a)), a.filename.rsplit("/", 1)[-1], ta)
            _walk(json.loads(copy.read(b)), a.filename.rsplit("/", 1)[-1], tb)
            out += [(fa, va, vb) for (fa, va), (_, vb) in zip(ta, tb)]
    return out
