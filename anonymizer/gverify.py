"""Compare a Takeout-style or TikTok export zip with its anonymized copy. Counts and field names only.

    python3 gverify.py <original.zip> <copy.zip>

1. Structure: same entries in the same order (names, folder flags, compression), same JSON keys / nesting /
   list lengths / value types, same CSV header / row and column counts, same HTML tag sequence.
2. Leak scan: every original value the copy replaced (JSON leaves, CSV cells, HTML tokens that changed) is
   searched in the whole copy: as a whole value, a token, or (6+ characters) a substring. Hits inside text the
   anonymizer wrote count as leaks; hits only inside unchanged text are overlaps with the platform's own wording.
"""
import collections
import csv
import io
import json
import re
import sys
import zipfile

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
oi, ci = orig.infolist(), copy.infolist()
diff = collections.Counter()
renamed_keys = collections.Counter()
replaced = collections.defaultdict(set)
derived, kept = [], collections.Counter()
derived_field = []
kept_values = []
TOK = re.compile(r"[^\s\"',;:!?()\[\]{}<>]+|[\w.@+\-]+")


def kind(v):
    if isinstance(v, str):
        return "empty" if v == "" else "url" if re.match(r"https?://", v) else "str"
    return type(v).__name__


TEMPLATES = [("Je hebt naar ", " gekeken"), ("Je hebt gezocht naar ", ""), ("Afbeelding bekeken van ", ""),
             ("Je hebt ", " bezocht"), ("Je hebt ", " bekeken"), ("Je hebt ", " gebruikt"), ("Je hebt ", " gelezen"),
             ("Watched ", ""), ("Searched for ", ""), ("Visited ", ""), ("Viewed ", ""), ("Je hebt ", "")]
URL_PART = re.compile(r"[^/?&=#:.+%]+")


def personal_parts(a, b, field):
    """The parts of a value that carry personal data: a template title's middle, a URL's changed parts."""
    if field.endswith("title"):
        for pre, suf in TEMPLATES:
            if all(x.startswith(pre) and x.endswith(suf) and len(x) > len(pre) + len(suf) for x in (a, b)):
                a, b = a[len(pre):len(a) - len(suf)], b[len(pre):len(b) - len(suf)]
                break
    if re.match(r"https?://", a) and re.match(r"https?://", b):
        pa, pb = URL_PART.findall(a), URL_PART.findall(b)
        if len(pa) == len(pb):
            return [(x, y) for x, y in zip(pa, pb) if x != y]
    return [(a, b)]


def leaf(a, b, field):
    if kind(a) != kind(b):
        diff["value kind " + kind(a) + "->" + kind(b)] += 1
    if isinstance(a, str) and a != b:
        for x, y in personal_parts(a, b, field):
            replaced[field].add(x)
            derived.append(y)
            derived_field.append((field, y, b, a))
    elif isinstance(a, str) and a:
        kept[field] += 1
        kept_values.append((field, a))


def compare(a, b, path):
    if type(a) is not type(b):
        diff["type"] += 1
        return
    if isinstance(a, dict):
        if len(a) != len(b):
            diff["key count"] += 1
        # compare by position: renamed keys (e.g. a username inside a key) are replaced values themselves
        for (ka, va), (kb, vb) in zip(a.items(), b.items()):
            if ka != kb:
                renamed_keys[path] += 1
                leaf(ka, kb, path + ".<key>")
            compare(va, vb, path + "." + (ka if ka == kb else "<renamed key>"))
    elif isinstance(a, list):
        if len(a) != len(b):
            diff["list length"] += 1
        for x, y in zip(a, b):
            compare(x, y, path + "[]")
    else:
        leaf(a, b, path)


print("entries:", len(oi), "->", len(ci))
names = collections.Counter()
for a, b in zip(oi, ci):
    names["same name" if a.filename == b.filename else "renamed"] += 1
    if a.is_dir() != b.is_dir():
        diff["folder flag"] += 1
    if a.compress_type != b.compress_type:
        diff["compression"] += 1
    if a.is_dir():
        continue
    fn = a.filename.rsplit("/", 1)[-1]
    da, db = orig.read(a), copy.read(b)
    if fn.endswith(".json"):
        compare(json.loads(da), json.loads(db), fn)
    elif fn.endswith(".csv"):
        ra, rb = list(csv.reader(io.StringIO(da.decode()))), list(csv.reader(io.StringIO(db.decode())))
        if ra[:1] != rb[:1] or len(ra) != len(rb) or any(len(x) != len(y) for x, y in zip(ra, rb)):
            diff["csv shape"] += 1
        for x, y in zip(ra[1:], rb[1:]):
            for c, (p, q) in enumerate(zip(x, y)):
                leaf(p, q, fn + ":" + ra[0][c])
    elif fn.endswith((".html", ".txt")):
        ta, tb = da.decode("utf-8", "replace"), db.decode("utf-8", "replace")
        if re.findall(r"<(/?\w+)", ta) != re.findall(r"<(/?\w+)", tb):
            diff["html tags"] += 1
        wa, wb = TOK.findall(ta), TOK.findall(tb)
        if len(wa) != len(wb):
            diff["html token count"] += 1
        for p, q in zip(wa, wb):
            leaf(p, q, fn + ":token")
    elif da == db:
        diff["binary identical"] += 1
print("entry names:", dict(names))
print("structure differences:", dict(diff) or "none")
print("renamed dict keys (by parent, field names only):", dict(renamed_keys) or "none")

parts = [b.filename for b in ci]
for b in ci:
    if b.is_dir():
        continue
    d = copy.read(b).decode("utf-8", "replace")
    if not b.filename.endswith(".json"):
        parts.append(d)
    if b.filename.endswith(".json"):
        def strings(n):
            if isinstance(n, dict):
                for k, v in n.items():
                    parts.append(k)
                    strings(v)
            elif isinstance(n, list):
                for x in n:
                    strings(x)
            elif isinstance(n, str):
                parts.append(n)
        strings(json.loads(d))
    elif b.filename.endswith(".csv"):
        for row in csv.reader(io.StringIO(d)):
            parts.extend(row)
corpus = "\n".join(parts).casefold()
values = {p.casefold() for p in parts}
tokens = set(TOK.findall(corpus))
dcorpus = "\n".join(derived).casefold()
dvalues = {x.casefold() for x in derived}
dtokens = set(TOK.findall(dcorpus))


def found(v, vals, toks, corp):
    c = v.casefold()
    return c in vals or c in toks or (len(c) >= 6 and c in corp)


allrep = set().union(*replaced.values()) - {""}
short = {v for v in allrep if len(v) < 4}
longv = allrep - short


def _check(chunk):
    return [(v, found(v, values, tokens, corpus), found(v, dvalues, dtokens, dcorpus)) for v in chunk]


import multiprocessing  # noqa: E402
_vals = sorted(longv)
_chunks = [_vals[k::56] for k in range(56)]
with multiprocessing.get_context("fork").Pool(12) as _pool:
    _res = [x for part in _pool.map(_check, _chunks) for x in part]
hits = {v for v, h, _ in _res if h}
_cand = {v for v, _, l in _res if l}
# a leak is an original piece that the anonymizer brought into a fake; a piece the fake kept from its own
# original (structure such as a JSON key, a kept host name) is reported as an overlap instead
leaks = set()
for v in _cand:
    c = v.casefold()
    for f, y, b, a in derived_field:
        yc = y.casefold()
        if (c == yc or c in TOK.findall(yc) or (len(c) >= 6 and c in yc)) and c not in a.casefold():
            leaks.add(v)
            break
print(f"  (candidates found inside generated text: {len(_cand)}; of those carried over from the fake's own original: "
      f"{len(_cand - leaks)})")
print(f"\nleak scan: {len(allrep)} distinct replaced values ({len(short)} shorter than 4 characters)")
print(f"  found anywhere in the copy: {len(hits)}; inside text the anonymizer wrote (a leak): {len(leaks)}")
print(f"  short values found anywhere: {sum(1 for v in short if found(v, values, tokens, corpus))}, "
      f"as a leak: {sum(1 for v in short if found(v, dvalues, dtokens, dcorpus))}")
if hits:
    by = collections.Counter(f for f, vals in replaced.items() for v in vals if v in hits)
    print("  fields of the hits (field names only):", dict(by.most_common(20)))
    lby = collections.Counter(f for f, vals in replaced.items() for v in vals if v in leaks)
    print("  fields of the leaks:", dict(lby.most_common(20)) or "none")
print("\nkept string values by field (field names only):")
for f, n in sorted(kept.items()):
    print(f"  {f}: {n}")

if "--explain" in sys.argv:
    import unicodedata
    def cls(v):
        return dict(collections.Counter("L" if c.isalpha() else "9" if c.isdigit() else "_" if c.isspace() else "." for c in v))
    owner = collections.defaultdict(list)   # derived text -> its field
    for f, vals in replaced.items():
        pass
    print("\nleaks explained (lengths and character classes only):")
    for v in sorted(leaks, key=len):
        c = v.casefold()
        how = "value" if c in dvalues else "token" if c in dtokens else "substring"
        fields = sorted(f for f, vals in replaced.items() if v in vals)
        where = [(f, len(y), c in a.casefold()) for f, y, b, a in derived_field if c in y.casefold()]
        print(f"  len {len(v)} {cls(v)} | replaced in {fields[:2]} | matched as {how} | inside fake part of "
              f"{sorted(set((f, n) for f, n, _ in where))[:3]} | that value's own original contained it: {[o for _, _, o in where][:3]}")

if "--overlaps" in sys.argv:
    print("\noverlaps (found only in unchanged text), by where they occur (field names only):")
    by = collections.Counter()
    kv = [(f, a.casefold()) for f, a in kept_values]
    names_cf = "\n".join(b.filename for b in ci).casefold()
    for v in hits - leaks:
        c = v.casefold()
        where = {f for f, a in kv if c == a or c in TOK.findall(a) or (len(c) >= 6 and c in a)}
        if not where:
            where = {"inside a fake, kept from its own original (structure)"} if any(
                c in a.casefold() and c in y.casefold() for f, y, b, a in derived_field) else (
                {"entry names"} if c in names_cf else {"JSON keys / other"})
        for w in where:
            by[re.sub(r"^[^:]*\.json", "json", w)] += 1
    for w, n in by.most_common(25):
        print(f"  {w}: {n}")
