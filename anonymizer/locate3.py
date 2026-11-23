"""For long (4+ chars) replaced originals that still occur in the copy: how they match (key/label, leaf, token,
substring) and where. Field names and lengths only, never values."""
import re
import sys
import zipfile
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import verify2_core as vc  # noqa: E402

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
pairs = vc.pairs(orig, copy)
c_leaves = vc.leaves(copy)
keys = set()


def k(n):
    if isinstance(n, dict):
        for kk, v in n.items():
            keys.add(vc.fix(kk).casefold())
            k(v)
    elif isinstance(n, list):
        for x in n:
            k(x)


for i in copy.infolist():
    if i.filename.endswith(".json"):
        k(json.loads(copy.read(i)))
names = "\n".join(i.filename for i in copy.infolist()).casefold()
replaced = {}
for f, a, b in pairs:
    if a != b and len(a) >= 4:
        replaced.setdefault(a, set()).add(f)
for v, fields in replaced.items():
    c = v.casefold()
    how = []
    if c in keys:
        how.append("equals a JSON key/label")
    leaf_hits = sorted({f for e, f, x in c_leaves if x.casefold() == c})
    if leaf_hits:
        how.append(f"equals copy leaf at {leaf_hits[:3]}")
    if c in names:
        how.append("inside an entry name")
    sub = sorted({f for e, f, x in c_leaves if c in x.casefold() and x.casefold() != c})
    if sub:
        how.append(f"inside copy leaf at {sub[:3]}")
    if how:
        print(f"len {len(v)} | replaced in {sorted(fields)[:2]} | " + "; ".join(how))
