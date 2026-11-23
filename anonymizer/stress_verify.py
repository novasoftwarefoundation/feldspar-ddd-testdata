"""Verify the rebuilt stress zip. Counts only.

    python3 stress_verify.py <stress-original> <stress-copy> <google-full-original> <google-full-anonymized>
"""
import collections
import csv
import io
import json
import re
import sys
import zipfile

so, sc, fo, fa = (zipfile.ZipFile(p) for p in sys.argv[1:5])
oi, ci = so.infolist(), sc.infolist()
print("entry list identical (names, order):", [i.filename for i in oi] == [i.filename for i in ci],
      "| folder flags identical:", [i.is_dir() for i in oi] == [i.is_dir() for i in ci],
      "| compression identical:", [i.compress_type for i in oi] == [i.compress_type for i in ci],
      "| dates identical:", [i.date_time for i in oi] == [i.date_time for i in ci], "| entries:", len(oi), len(ci))
anon = {i.filename: fa.read(i) for i in fa.infolist() if not i.is_dir()}
base = lambda n: re.sub(r" copy(?: \d+)?(?=/|\.\w+$|$)", "", n)
c = collections.Counter()
meta_text = []
for a, b in zip(oi, ci):
    if a.is_dir():
        continue
    db = sc.read(b)
    if a.filename.startswith("__MACOSX/") or a.filename.endswith(".DS_Store"):
        da = so.read(a)
        c["metadata entry identical to original" if da == db else "metadata entry changed (macl)"] += 1
        meta_text += [db.decode("latin1"), db.decode("utf-16-be", "replace"), db[1:].decode("utf-16-be", "replace")]
    else:
        c["data entry identical to anonymized google-full" if db == anon[base(a.filename)] else "DATA ENTRY DIFFERS"] += 1
print(dict(c))

# leak scan of the metadata entries: every original google-full value (4+ chars) that the anonymized copy replaced
orig_vals, anon_vals = set(), set()
def strings(n, out):
    if isinstance(n, dict):
        for k, v in n.items():
            out.add(k); strings(v, out)
    elif isinstance(n, list):
        for x in n:
            strings(x, out)
    elif isinstance(n, str):
        out.add(n)
for z, out in ((fo, orig_vals), (fa, anon_vals)):
    for i in z.infolist():
        if i.filename.endswith(".json"):
            strings(json.loads(z.read(i)), out)
        elif i.filename.endswith(".csv"):
            for row in csv.reader(io.StringIO(z.read(i).decode())):
                out.update(row)
replaced = {v for v in orig_vals - anon_vals if len(v) >= 4}
# and the personal parts of template titles
for v in list(replaced):
    m = re.match(r"^(Je hebt naar |Je hebt gezocht naar |Je hebt |Afbeelding bekeken van )(.*?)( gekeken| bezocht)?$", v)
    if m and len(m.group(2)) >= 4:
        replaced.add(m.group(2))
meta = "\n".join(meta_text).casefold()
print("replaced google-full values (and title parts) checked in the metadata entries:", len(replaced),
      "| found:", sum(1 for v in replaced if v.casefold() in meta))
