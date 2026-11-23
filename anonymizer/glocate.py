"""For Takeout leak hits: how they match and how long their personal part is. Counts and lengths only."""
import collections
import json
import re
import sys
import zipfile
from urllib.parse import urlsplit

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import takeout as tk  # noqa: E402

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
TOK = re.compile(r"[^\s\"',;:!?()\[\]{}<>]+|[\w.@+\-]+")
pairs, derived = [], []
for a, b in zip(orig.infolist(), copy.infolist()):
    if a.filename.endswith(".json"):
        for ra, rb in zip(json.loads(orig.read(a)), json.loads(copy.read(b))):
            for k in ("title", "titleUrl"):
                if k in ra:
                    pairs.append((a.filename.rsplit("/", 1)[-1] + ":" + k, ra[k], rb[k]))
            for x, y in zip(ra.get("subtitles", []), rb.get("subtitles", [])):
                pairs.append(("subtitles", x.get("name", ""), y.get("name", "")))
derived = [b for _, a, b in pairs if a != b]
dvals = {d.casefold() for d in derived}
dtoks = set(TOK.findall("\n".join(derived).casefold()))
dcorp = "\n".join(derived).casefold()


def personal_part(field, v):
    if field.endswith("titleUrl"):
        q = urlsplit(v).query
        return "&".join(x.partition("=")[2] for x in q.split("&")) if q else urlsplit(v).path
    for pre, suf in tk.TEMPLATES:
        if v.startswith(pre) and v.endswith(suf) and len(v) > len(pre) + len(suf):
            return v[len(pre):len(v) - len(suf)]
    return v


out = collections.Counter()
for field, a, b in pairs:
    if a == b or len(a) < 4:
        continue
    c = a.casefold()
    how = "value" if c in dvals else "token" if c in dtoks else "substring" if (len(c) >= 6 and c in dcorp) else None
    if how:
        part = personal_part(field, a)
        p = part.casefold()
        part_hit = p in dvals or p in dtoks or (len(p) >= 4 and p in dcorp)
        out[(field, how, "personal part len %d" % len(part), "personal part found: %s" % part_hit)] += 1
for k, n in sorted(out.items()):
    print(n, k)
