"""Where each label occurs (file name, count) and, with MASK=1, its value lengths and masked shapes (letters as
a/A, digits as 9, other characters as *). Prints no values; use it to decide whether a label is a setting or data.

    [MASK=1] python3 nl_probe.py <export.zip> <label> [<label> ...]
"""
import json, re, sys, zipfile, collections
def fix(s):
    try: return s.encode("latin1").decode("utf-8")
    except Exception: return s
def mask(v):
    v = fix(v)
    m = re.sub(r"[A-Z]", "A", re.sub(r"[a-z]", "a", re.sub(r"\d", "9", v)))
    m = re.sub(r"[^\x00-\x7f]", "*", m)
    m = re.sub(r"(a)\1{2,}", "a+", re.sub(r"(9)\1{2,}", "9+", m))
    return m[:24]
z = zipfile.ZipFile(sys.argv[1]); want = set(sys.argv[2:])
where = collections.defaultdict(collections.Counter); shapes = collections.defaultdict(collections.Counter)
def walk(n, f, lab=None):
    if isinstance(n, dict):
        l = fix(n["label"]) if isinstance(n.get("label"), str) else None
        for k, v in n.items():
            if k == "string_map_data" and isinstance(v, dict):
                for mk, mv in v.items(): walk(mv, f, fix(mk))
            elif k in ("value",) and l: walk(v, f, l)
            elif k == "value" and lab: walk(v, f, lab)
            elif k != "label": walk(v, f, None)
    elif isinstance(n, list):
        for x in n: walk(x, f, lab)
    elif isinstance(n, str) and lab in want:
        where[lab][re.sub(r"_\d+", "_N", f.rsplit("/", 1)[-1])] += 1
        shapes[lab]["empty" if n == "" else "len%d" % min(len(n), 99)] += 1
        if MASK: shapes[lab]["mask:" + mask(n)] += 1
MASK = bool(int(__import__("os").environ.get("MASK", "0")))
for i in z.infolist():
    if i.filename.endswith(".json"): walk(json.loads(z.read(i)), i.filename)
for lab in sorted(want):
    print(lab, dict(where[lab]))
    if MASK: print("   ", dict(shapes[lab].most_common(6)))
