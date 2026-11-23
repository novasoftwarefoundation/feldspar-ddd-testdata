"""What do .DS_Store and AppleDouble entries hold? Masked formats and counts only."""
import collections
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
names = set()
for i in z.infolist():
    for p in i.filename.rstrip("/").split("/"):
        names.add(p)
        names.add(p[2:] if p.startswith("._") else p)
mask = lambda s: re.sub(r"[^\W\d_]+", lambda m: "A" if m.group()[0].isupper() else "a", re.sub(r"[0-9a-fA-F]{8,}", "<HEX>", re.sub(r"\d+", "9", s)))
ds = collections.Counter()
ds_other = collections.Counter()
qformat = collections.Counter()
macl = collections.Counter()
for i in z.infolist():
    fn = i.filename.rsplit("/", 1)[-1]
    if fn == ".DS_Store" and not i.filename.startswith("__MACOSX/"):
        d = z.read(i)
        # .DS_Store records: big-endian length-prefixed UTF-16 file names
        recs = set()
        for m in re.finditer(rb"((?:\x00[\x20-\x7e]){2,})", d):
            recs.add(m.group(1).decode("utf-16-be"))
        ds["files"] += 1
        for r in recs:
            ds["names matching archive entries" if r in names else "other strings"] += 1
            if r not in names:
                ds_other[mask(r)] += 1
    elif i.filename.startswith("__MACOSX/") and not i.is_dir():
        d = z.read(i)
        for m in re.finditer(rb"com\.apple\.quarantine\x00", d):
            pass
        q = re.search(rb"(\d{4};[0-9a-f]{8};[^;\x00]*;[0-9A-F-]*)", d)
        if q:
            qformat[mask(q.group(1).decode("latin1"))] += 1
        if b"com.apple.macl" in d:
            macl["entries with macl"] += 1
print("DS_Store:", dict(ds))
print("DS_Store other strings (masked):", ds_other.most_common(15))
print("quarantine value formats (masked):", qformat.most_common(6))
print(dict(macl))
