"""Which replaced originals occur inside replacement text, and where? Field names, lengths, classes only."""
import re
import sys
import unicodedata
import zipfile
import collections

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import verify2_core as vc  # noqa: E402

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
pairs = vc.pairs(orig, copy)
derived = [(f, b) for f, a, b in pairs if a != b]
for a, b in zip(orig.infolist(), copy.infolist()):
    for x, y in zip(a.filename.rstrip("/").split("/"), b.filename.rstrip("/").split("/")):
        if x != y:
            derived.append(("<entry name>", y))
replaced = collections.defaultdict(set)
for f, a, b in pairs:
    if a != b and a:
        replaced[a].add(f)


def classes(v):
    c = collections.Counter()
    for ch in v:
        cat = unicodedata.category(ch)
        c["letter" if cat[0] == "L" else "digit" if cat == "Nd" else "emoji" if cat == "So" else "space" if ch.isspace() else "punct"] += 1
    return dict(c)


tok = re.compile(r"[^\s\"',;:!?()\[\]{}<>]+|[\w.@+\-]+")
for v, fields in replaced.items():
    c = v.casefold()
    where = set()
    for f, b in derived:
        bc = b.casefold()
        if bc == c or c in tok.findall(bc) or (len(c) >= 6 and c in bc):
            where.add(f)
    if where:
        same_kind = [f for f in where if f in fields]
        print(f"len {len(v)} {classes(v)} | replaced in {sorted(fields)[:2]} | appears in replacement text of {sorted(where)[:3]}"
              f" | the original's own field among them: {bool(same_kind)}")
