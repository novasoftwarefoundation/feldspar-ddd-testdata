# Where do the flagged originals occur in the copy? Prints file + field path + value length, never values.
import sys, os, re, json, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import anonymize as an
orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
fix = lambda s: an.unmoji(s)[0]
def leaves(n, p, out):
    if isinstance(n, dict):
        for k, v in n.items(): leaves(v, p + "." + fix(k), out)
    elif isinstance(n, list):
        for x in n: leaves(x, p + "[]", out)
    elif isinstance(n, str): out.append((p, fix(n)))
so = []
for a in orig.infolist():
    if a.filename.endswith(".json"):
        d = json.loads(orig.read(a)); an.collect(d); leaves(d, a.filename, so)
vals = [v for _, v in so]
phones = {s for s in vals if an.PHONE_RE.match(s) and sum(c.isdigit() for c in s) >= 6}
names = {n for n in an.NAMES if len(n) >= 4 and " " in n}
sc = []
for b in copy.infolist():
    if b.filename.endswith(".json"): leaves(json.loads(copy.read(b)), re.sub(r"(inbox|message_requests)/[^/]+", r"\1/T", b.filename), sc)
toks = {}
for p, v in sc:
    for t in re.findall(r"[\w.@+\-:]+", v.casefold()): toks.setdefault(t, set()).add(p)
for v in phones:
    if v.casefold() in toks:
        origpaths = {re.sub(r"(inbox|message_requests)/[^/]+", r"\1/T", p) for p, x in so if x == v}
        print("phone-like hit: len", len(v), "| in copy at", sorted(toks[v.casefold()])[:3], "| in original at", sorted(origpaths)[:3])
for n in names:
    hits = [p for p, x in sc if n.casefold() in x.casefold()]
    if hits:
        origpaths = sorted({re.sub(r"(inbox|message_requests)/[^/]+", r"\1/T", p) for p, x in so if x == n})
        print("name hit: words", len(n.split()), "| in copy at", sorted(set(hits))[:3], "| in original at", origpaths[:3])
pi = json.loads(orig.read("personal_information/personal_information/personal_information.json"))["profile_user"][0]
for k in ("Gender", "Private Account", "Emoji Pong High Score"):
    v = fix(pi["string_map_data"][k]["value"]).casefold()
    whole = sum(1 for p, x in sc if x.casefold() == v)
    print(k, "| len", len(v), "| copy leaves equal to it:", whole, "| original leaves equal to it:", sum(1 for p, x in so if x.casefold() == v))
