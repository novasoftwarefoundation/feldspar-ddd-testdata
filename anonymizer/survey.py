"""Survey a Meta export zip: field labels with value shapes, title stats, key paths. Never prints values."""
import json, re, sys, zipfile, collections
def fix(s):
    try: return s.encode("latin1").decode("utf-8")
    except Exception: return s
def shape(v):
    if not isinstance(v, str): return type(v).__name__
    if v == "": return "empty"
    if re.match(r"https?://", v): return "url"
    if re.fullmatch(r"-?\d+(\.\d+)?", v): return "num"
    if re.fullmatch(r"\S+@\S+\.\S+", v): return "email"
    if v in ("True", "False", "true", "false"): return "bool"
    return "text"
z = zipfile.ZipFile(sys.argv[1]); mode = sys.argv[2]
stats = collections.defaultdict(collections.Counter); keys = collections.defaultdict(collections.Counter)
labels = set(); titles = collections.defaultdict(collections.Counter)
def walk(n, f, p, lab=None):
    if isinstance(n, dict):
        if isinstance(n.get("label"), str):
            labels.add(n["label"]); l = fix(n["label"])
            for k in ("value", "href"):
                if k in n: stats[(l, k)][shape(n[k])] += 1
            for it in n.get("vec") or []:
                if isinstance(it, dict) and "value" in it: stats[(l, "vec")][shape(it["value"])] += 1
        smd = n.get("string_map_data")
        if isinstance(smd, dict):
            labels.update(smd.keys())
            for k, e in smd.items():
                for kk in ("value", "href"):
                    if kk in e: stats[("SMD:" + fix(k), kk)][shape(e[kk])] += 1
        if isinstance(n.get("title"), str) and n["title"]: titles[(f, p)][n["title"]] += 1
        for k, v in n.items(): walk(v, f, p + "." + k)
    elif isinstance(n, list):
        for x in n: walk(x, f, p + "[]")
    else:
        keys[re.sub(r"\.string_map_data\.[^.]+", ".smd.<L>", p)][shape(n)] += 1
for i in z.infolist():
    if i.filename.endswith(".json"):
        f = re.sub(r"(inbox|message_requests)/[^/]+", r"\1/<T>", i.filename)
        walk(json.loads(z.read(i)), f.split("/")[-1], "$")
if mode == "labels":
    for (l, k), c in sorted(stats.items()): print(f"{l} | {k} | {dict(c)}")
elif mode == "keys":
    for k, c in sorted(keys.items()): print(k, dict(c))
elif mode == "titles":
    for (f, p), c in sorted(titles.items()):
        heads = sorted(fix(t) for t, n in c.items() if t in labels or (n >= 3 and len(c) <= 7))
        print(f"{f} {p}: total={sum(c.values())} distinct={len(c)} heading-like={heads}")
