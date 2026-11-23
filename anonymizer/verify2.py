"""Compare an export zip with its anonymized copy. Prints counts and field names only, never a value.

    python3 verify2.py <original.zip> <copy.zip> [--own-file <entry name suffix> ...]

1. Structure: same entries in the same order (directory flag, depth, extension, and every path part that
   was not renamed), same JSON keys / nesting / list lengths / value types, same media types.
2. Leak scan: every original string value that the copy replaced, and every renamed path part, is searched
   in the copy (entry names, JSON text decoded, other text files): as a whole value, as a whole token, and
   (for values of 6+ characters) as a substring. All values of the --own-file entries (the account's own
   profile files) are searched too, replaced or not.
"""
import collections
import json
import re
import sys
import zipfile

args = sys.argv[1:]
own_files = []
if "--own-file" in args:
    i = args.index("--own-file")
    own_files = args[i + 1:]
    args = args[:i]
orig, copy = zipfile.ZipFile(args[0]), zipfile.ZipFile(args[1])
oi, ci = orig.infolist(), copy.infolist()


def fix(s):
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def kind(v):
    if isinstance(v, str):
        return "empty" if v == "" else "url" if re.match(r"https?://", v) else "str"
    return type(v).__name__


def media_sig(d):
    if d[:3] == b"\xff\xd8\xff":
        return "jpg"
    if d[:4] == b"\x89PNG":
        return "png"
    if d[8:12] == b"WEBP":
        return "webp"
    if d[4:8] == b"ftyp":
        return "mp4" + ("v" if b"vide" in d else "") + ("a" if b"soun" in d else "")
    return "other"


diff = collections.Counter()
replaced = collections.defaultdict(set)     # field -> original values that were replaced
derived = []                                # copy text written by the anonymizer (replacement values)
kept = collections.Counter()                # field -> kept non-trivial string leaves
renamed_parts = set()


def field_of(path):
    return re.sub(r"\[\]", "", path)


def compare(a, b, path):
    if type(a) is not type(b):
        diff["type"] += 1
        return
    if isinstance(a, dict):
        if list(a.keys()) != list(b.keys()):
            diff["keys"] += 1
        for k in a:
            if k in b:
                if k == "string_map_data" and isinstance(a[k], dict):
                    for mk in a[k]:
                        compare(a[k][mk], b[k].get(mk), path + ".smd:" + fix(mk))
                elif isinstance(a.get("label"), str) and k in ("value", "href", "vec"):
                    compare(a[k], b[k], path + ".label:" + fix(a["label"]) + "." + k)
                else:
                    compare(a[k], b[k], path + "." + k)
    elif isinstance(a, list):
        if len(a) != len(b):
            diff["list_length"] += 1
        for x, y in zip(a, b):
            compare(x, y, path + "[]")
    else:
        if kind(a) != kind(b):
            diff["string_kind:" + kind(a) + "->" + kind(b)] += 1
        if isinstance(a, str) and a != b:
            replaced[field_of(path)].add(fix(a))
            derived.append(fix(b))
        elif isinstance(a, str) and a and a not in ("True", "False", "true", "false"):
            kept[field_of(path)] += 1


print("entries:", len(oi), "->", len(ci))
name_diff = collections.Counter()
for a, b in zip(oi, ci):
    pa, pb = a.filename.rstrip("/").split("/"), b.filename.rstrip("/").split("/")
    if a.is_dir() != b.is_dir() or len(pa) != len(pb):
        name_diff["dir flag or depth differs"] += 1
        continue
    if pa[-1].rpartition(".")[2] != pb[-1].rpartition(".")[2] and "." in pa[-1]:
        name_diff["extension differs"] += 1
    for x, y in zip(pa, pb):
        if x != y:
            renamed_parts.add(x)
            derived.append(y)
    name_diff["same" if a.filename == b.filename else "renamed part(s)"] += 1
    if a.is_dir():
        continue
    fn = a.filename.rsplit("/", 1)[-1]
    if fn.endswith(".json"):
        compare(json.loads(orig.read(a)), json.loads(copy.read(b)), fn)
    else:
        da, db = orig.read(a), copy.read(b)
        if fn.endswith(".txt") or fn.endswith((".csv", ".html")):
            if da != db:
                diff["text file changed"] += 1
        elif media_sig(da) != media_sig(db):
            diff["media_type"] += 1
        elif da == db:
            diff["media_bytes_identical"] += 1
print("entry names:", dict(name_diff), "| distinct renamed path parts:", len(renamed_parts))
print("structure differences:", dict(diff) or "none")

# corpus of the copy
parts, leaves = [b.filename for b in ci], []


def strings(n, out):
    if isinstance(n, dict):
        for k, v in n.items():
            out.append(fix(k))
            strings(v, out)
    elif isinstance(n, list):
        for x in n:
            strings(x, out)
    elif isinstance(n, str):
        out.append(fix(n))


for b in ci:
    if b.is_dir():
        continue
    d = copy.read(b)
    if b.filename.endswith(".json"):
        parts.append(d.decode("utf-8"))
        strings(json.loads(d), leaves)
    elif b.filename.endswith((".txt", ".csv", ".html")):
        parts.append(d.decode("utf-8", "replace"))
parts += leaves
corpus = "\n".join(parts).casefold()
leafset = {x.casefold() for x in leaves}
tokens = set(re.findall(r"[^\s\"',;:!?()\[\]{}<>]+", corpus))
tokens |= set(re.findall(r"[\w.@+\-]+", corpus))


def hits(values):
    exact = tok = sub = 0
    for v in values:
        c = v.casefold()
        if c in leafset:
            exact += 1
        elif c in tokens:
            tok += 1
        elif len(c) >= 6 and c in corpus:
            sub += 1
    return exact, tok, sub


dcorpus = "\n".join(derived).casefold()
dleaves = {x.casefold() for x in derived}
dtokens = set(re.findall(r"[^\s\"',;:!?()\[\]{}<>]+", dcorpus)) | set(re.findall(r"[\w.@+\-]+", dcorpus))


def leak_hits(values):
    """Original values inside text the anonymizer wrote (a real leak, not an overlap with kept wording)."""
    n = 0
    for v in values:
        c = v.casefold()
        if c in dleaves or c in dtokens or (len(c) >= 6 and c in dcorpus):
            n += 1
    return n


allrep = set().union(*replaced.values()) if replaced else set()
allrep.discard("")
short = {v for v in allrep if len(v) < 4}
e, t, s = hits(allrep - short)
print(f"\nleak scan: {len(allrep)} distinct replaced values ({len(short)} shorter than 4 characters)")
print(f"  found in the copy: as a whole value {e}, as a token {t}, as a substring (6+ chars) {s}")
e2, t2, _ = hits(short)
print(f"  short values (<4 chars) found as a whole value {e2}, as a token {t2}")
if e or t or s:
    print("  fields of the hits (field names only):")
    by = collections.Counter()
    for f, vals in replaced.items():
        for v in vals:
            if len(v) >= 4 and hits([v]) != (0, 0, 0):
                by[f] += 1
    for f, n in by.most_common(30):
        print(f"    {f}: {n}")
print(f"  of those, inside text the anonymizer wrote (a leak): {leak_hits(allrep - short)} "
      f"(short values: {leak_hits(short)}); the rest only overlap Meta's own unchanged wording, keys or folder names")
rp = {p for p in renamed_parts if len(p) >= 4}
print(f"  renamed path parts: {len(rp)} distinct, found in the copy {sum(1 for p in rp if p.casefold() in corpus)}")

for suffix in own_files:
    vals = []
    for a in oi:
        if a.filename.endswith(suffix):
            tmp = []
            strings(json.loads(orig.read(a)), tmp)
            vals += tmp
    keys = set()
    for a in oi:
        if a.filename.endswith(suffix):
            def k(n):
                if isinstance(n, dict):
                    for kk, v in n.items():
                        keys.add(fix(kk))
                        if kk == "label" and isinstance(v, str):
                            keys.add(fix(v))
                        k(v)
                elif isinstance(n, list):
                    for x in n:
                        k(x)
            k(json.loads(orig.read(a)))
    vals = {v for v in vals if v and v not in keys and v not in ("True", "False", "true", "false")}
    e, t, s = hits({v for v in vals if len(v) >= 4})
    print(f"  own file {suffix}: {len(vals)} values; found as whole value {e}, token {t}, substring {s}"
          f"; values under 4 chars: {sum(1 for v in vals if len(v) < 4)}")

print("\nkept string values by field (field names only, for review):")
for f, n in sorted(kept.items()):
    print(f"  {f}: {n}")
