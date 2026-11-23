"""Explain metadata hits: lengths, classes, and whether each is part of an archive entry name. No values."""
import sys, re, json, csv, io, zipfile, collections
exec(open(__file__.replace("stress_locate.py", "stress_verify.py")).read().split("meta = ")[0].split("print(\"entry list")[0])
so, sc, fo, fa = (zipfile.ZipFile(p) for p in sys.argv[1:5])
orig_vals, anon_vals = set(), set()
def strings(n, out):
    if isinstance(n, dict):
        for k, v in n.items(): out.add(k); strings(v, out)
    elif isinstance(n, list):
        for x in n: strings(x, out)
    elif isinstance(n, str): out.add(n)
for z, out in ((fo, orig_vals), (fa, anon_vals)):
    for i in z.infolist():
        if i.filename.endswith(".json"): strings(json.loads(z.read(i)), out)
        elif i.filename.endswith(".csv"):
            for row in csv.reader(io.StringIO(z.read(i).decode())): out.update(row)
replaced = {v for v in orig_vals - anon_vals if len(v) >= 4}
for v in list(replaced):
    m = re.match(r"^(Je hebt naar |Je hebt gezocht naar |Je hebt |Afbeelding bekeken van )(.*?)( gekeken| bezocht)?$", v)
    if m and len(m.group(2)) >= 4: replaced.add(m.group(2))
names = "\n".join(i.filename for i in sc.infolist()).casefold()
ds, ad = [], []
for i in sc.infolist():
    if i.is_dir(): continue
    if i.filename.endswith(".DS_Store") and not i.filename.startswith("__MACOSX/"):
        d = sc.read(i); ds += [d.decode("latin1"), d.decode("utf-16-be", "replace"), d[1:].decode("utf-16-be", "replace")]
    elif i.filename.startswith("__MACOSX/"):
        d = sc.read(i); ad += [d.decode("latin1"), d.decode("utf-16-be", "replace"), d[1:].decode("utf-16-be", "replace")]
ds, ad = "\n".join(ds).casefold(), "\n".join(ad).casefold()
for v in replaced:
    c = v.casefold()
    if c in ds or c in ad:
        print(f"len {len(v)} letters-only {v.isalpha()} | in .DS_Store {c in ds} | in AppleDouble {c in ad} | part of an archive entry name {c in names}")
