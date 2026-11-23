"""For verify2 hits: where in the copy does each replaced original occur? Field names, lengths and
character classes only, never values.

    python3 locate2.py <original.zip> <copy.zip> [own-file suffix ...]
"""
import re
import sys
import unicodedata
import zipfile
import json
import collections

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import verify2_core as vc  # noqa: E402

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
own = sys.argv[3:]
o_leaves, c_leaves = vc.leaves(orig), vc.leaves(copy)   # lists of (entry, field, value)
pairs = vc.pairs(orig, copy)                             # (field, orig value, copy value)
replaced = {}
for f, a, b in pairs:
    if a != b and a:
        replaced.setdefault(a, set()).add(f)
by_value = collections.defaultdict(list)
for e, f, v in c_leaves:
    by_value[v.casefold()].append(f)


def classes(v):
    c = collections.Counter()
    for ch in v:
        cat = unicodedata.category(ch)
        c["letter" if cat[0] == "L" else "digit" if cat == "Nd" else "emoji" if cat == "So" else "space" if ch.isspace() else "punct"] += 1
    return dict(c)


print("replaced originals found in the copy:")
for v, fields in replaced.items():
    where = by_value.get(v.casefold())
    if where and (len(v) >= 4 or True):
        kept_there = sum(1 for f, a, b in pairs if a == v and a == b)
        print(f"  len {len(v)} {classes(v)} | replaced in {sorted(fields)[:2]} | equal leaf in copy at {sorted(set(where))[:3]}"
              f" | kept unchanged at {kept_there} place(s)")
print("\nkept leaves in text/name fields (character classes only):")
for f, a, b in pairs:
    if a == b and a and (f.endswith("messages.content") or "Vorname" in f or "Nachname" in f):
        print(f"  {f}: len {len(a)} {classes(a)}")
for suffix in own:
    for e, f, v in o_leaves:
        if e.endswith(suffix) and v and v.casefold() in by_value:
            print(f"own file {suffix}: field {f} (len {len(v)}) occurs as a whole value in the copy at {sorted(set(by_value[v.casefold()]))[:3]}")
