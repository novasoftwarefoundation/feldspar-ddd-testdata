"""Verify the anonymized ChatGPT error cases. Counts and field names only.

    python3 cg_verify.py <orig-dir> <copy-dir>      (each copy has the same file name as its original)

1. Per case: same entries in the same order (names equal apart from mapped ids); for every JSON-ish entry the
   skeleton (all bytes outside string-literal contents) is byte-identical, so the breakage is kept exactly;
   attachments keep their type.
2. Leak scan over all copies together: every replaced original value (literal level; for URLs the changed
   parts) and every renamed name part, searched in all copies; leaks = inside text the anonymizer wrote and not
   carried over from the fake's own original.
"""
import collections
import glob
import json
import os
import re
import sys
import zipfile

LIT = re.compile(r'"(?:[^"\\\n]|\\.)*"')
TOK = re.compile(r"[^\s\"',;:!?()\[\]{}<>]+|[\w.@+\-]+")
URL_PART = re.compile(r"[^/?&=#:.+%]+")
odir, cdir = sys.argv[1:3]


def lits(t):
    out = []
    for m in LIT.finditer(t):
        try:
            out.append((m, json.loads(m.group())))
        except ValueError:
            pass
    return out


def skeleton(t):
    return LIT.sub('""', t)


def sig(d):
    return ("png" if d[:4] == b"\x89PNG" else "webp" if d[8:12] == b"WEBP" else "pdf" if d[:4] == b"%PDF" else
            "jpg" if d[:3] == b"\xff\xd8\xff" else "json-text" if d[:1] in (b"[", b"{") else "other")


replaced, derived_field, kept, parts = collections.defaultdict(set), [], collections.Counter(), []
for op in sorted(glob.glob(os.path.join(odir, "*.zip"))):
    cp = os.path.join(cdir, os.path.basename(op))
    oz, cz = zipfile.ZipFile(op), zipfile.ZipFile(cp)
    oi, ci = oz.infolist(), cz.infolist()
    c = collections.Counter()
    c["entries %d -> %d" % (len(oi), len(ci))] += 1
    for a, b in zip(oi, ci):
        c["name same" if a.filename == b.filename else "name: id mapped"] += 1
        if a.filename != b.filename:
            if re.sub(r"[0-9a-f]", "x", a.filename) != re.sub(r"[0-9a-f]", "x", b.filename):
                c["NAME SHAPE CHANGED"] += 1
            replaced["<entry name>"].add(a.filename)
            derived_field.append(("<entry name>", b.filename, a.filename))
        parts.append(b.filename)
        da, db = oz.read(a), cz.read(b)
        if sig(da) in ("json-text", "other") or a.filename.endswith((".json", ".html")):
            ta, tb = da.decode("utf-8", "replace"), db.decode("utf-8", "replace")
            c["skeleton identical" if skeleton(ta) == skeleton(tb) else "SKELETON DIFFERS"] += 1
            la, lb = lits(ta), lits(tb)
            if len(la) != len(lb):
                c["LITERAL COUNT DIFFERS"] += 1
            key = None
            for (ma, sa), (mb, sb) in zip(la, lb):
                j = ma.end()
                while j < len(ta) and ta[j] in " \t\r\n":
                    j += 1
                is_key = j < len(ta) and ta[j] == ":"
                field = a.filename.rsplit("/", 1)[-1] + ":" + ("<key>" if is_key else (key or "?"))
                if is_key:
                    key = "<id-key>" if re.search(r"[0-9a-f]{8}-|file[-_]|\d{6,}", sa) else sa
                if not isinstance(sa, str):
                    continue
                parts.append(sb)
                if sa != sb:
                    if re.match(r"https?://", sa) and re.match(r"https?://", sb):
                        pa, pb = URL_PART.findall(sa), URL_PART.findall(sb)
                        pairs = [(x, y) for x, y in zip(pa, pb) if x != y] if len(pa) == len(pb) else [(sa, sb)]
                    else:
                        pairs = [(sa, sb)]
                    for x, y in pairs:
                        replaced[field].add(x)
                        derived_field.append((field, y, sa))
                elif sa:
                    kept[field] += 1
            if not la:
                parts.append(tb)
                c["no string literals (kept byte for byte)" if ta == tb else "TEXT CHANGED"] += 1
        else:
            c["attachment type kept" if sig(da) == sig(db) else "ATTACHMENT TYPE CHANGED"] += 1
            c["attachment bytes identical" if da == db else "attachment replaced"] += 1
    print(os.path.basename(cp), dict(c))

corpus = "\n".join(parts).casefold()
values = {p.casefold() for p in parts}
tokens = set(TOK.findall(corpus))
dcorpus = "\n".join(y for _, y, _ in derived_field).casefold()
allrep = set().union(*replaced.values()) - {""}
short = {v for v in allrep if len(v) < 4}
longv = allrep - short


def anywhere(v):
    c = v.casefold()
    return c in values or c in tokens or (len(c) >= 6 and c in corpus)


hits = {v for v in longv if anywhere(v)}
leaks = set()
for v in hits:
    c = v.casefold()
    if not (c in dcorpus):
        continue
    for f, y, a in derived_field:
        yc = y.casefold()
        if (c == yc or c in TOK.findall(yc) or (len(c) >= 6 and c in yc)) and c not in a.casefold():
            leaks.add(v)
            break
print(f"\nleak scan over all copies: {len(allrep)} distinct replaced values ({len(short)} shorter than 4 characters)")
print(f"  found anywhere: {len(hits)}; inside text the anonymizer wrote (a leak): {len(leaks)}")
print(f"  short values found anywhere: {sum(1 for v in short if anywhere(v))}")
if hits:
    print("  fields of the hits:", dict(collections.Counter(f for f, vs in replaced.items() for v in vs if v in hits).most_common(15)))
    print("  fields of the leaks:", dict(collections.Counter(f for f, vs in replaced.items() for v in vs if v in leaks).most_common(15)) or "none")
print("\nkept literal values by field (field names only):")
for f, n in sorted(kept.items()):
    print(f"  {f}: {n}")

if "--where" in sys.argv:
    print("\nwhere the hits occur in the copies (entry and field names only):")
    loc = collections.Counter()
    for cp in sorted(glob.glob(os.path.join(cdir, "*.zip"))):
        cz = zipfile.ZipFile(cp)
        for b in cz.infolist():
            t = cz.read(b).decode("utf-8", "replace")
            if sig(cz.read(b)) not in ("json-text", "other") and not b.filename.endswith((".json", ".html")):
                continue
            ls = lits(t)
            key = None
            spans = [(m.start(), m.end()) for m, _ in ls]
            for m, s in ls:
                j = m.end()
                while j < len(t) and t[j] in " \t\r\n":
                    j += 1
                if j < len(t) and t[j] == ":":
                    key = "<id-key>" if re.search(r"[0-9a-f]{8}-|file[-_]|\d{6,}", s) else s
                    continue
                if isinstance(s, str):
                    sc = s.casefold()
                    for v in hits:
                        c = v.casefold()
                        if c == sc or c in TOK.findall(sc) or (len(c) >= 6 and c in sc):
                            loc[(b.filename.rsplit("/", 1)[-1] if not re.search(r"file_", b.filename) else "<attachment>", key)] += 1
            outside = LIT.sub("", t).casefold()
            for v in hits:
                if v.casefold() in outside:
                    loc[(b.filename.rsplit("/", 1)[-1], "<outside string literals>")] += 1
    for k, n in loc.most_common(20):
        print(" ", n, k)
    for cp in sorted(glob.glob(os.path.join(cdir, "*.zip")))[:1]:
        oz = zipfile.ZipFile(os.path.join(odir, os.path.basename(cp)))
        cz = zipfile.ZipFile(cp)
        for a, b in zip(oz.infolist(), cz.infolist()):
            ta, tb = oz.read(a).decode("utf-8", "replace"), cz.read(b).decode("utf-8", "replace")
            if (a.filename.endswith((".json", ".html")) or sig(oz.read(a)) == "json-text") and skeleton(ta) != skeleton(tb):
                print("  skeleton differs in:", a.filename.rsplit("/", 1)[-1] if "file_" not in a.filename else "<attachment>")
    print("\nfields of hits that occur outside string literals in the copies:")
    oc = collections.Counter()
    outs = []
    for cp in sorted(glob.glob(os.path.join(cdir, "*.zip"))):
        cz = zipfile.ZipFile(cp)
        for b in cz.infolist():
            if b.filename.endswith((".json", ".html")):
                outs.append(LIT.sub("", cz.read(b).decode("utf-8", "replace")).casefold())
    outside_all = "\n".join(outs)
    for f, vs in replaced.items():
        for v in vs:
            if v in hits and v.casefold() in outside_all:
                oc[(f, "len %d" % len(v), "letters-only" if v.isalpha() else "mixed")] += 1
    for k, n in oc.most_common(20):
        print(" ", n, k)
    print("\nmanifest-path hits, how they match (lengths/kinds only):")
    for f in ("export_manifest.json:path", "export_manifest.json:files", "library_files.json:<id-key>", "conversation_asset_file_names.json:<id-key>"):
        for v in replaced.get(f, ()):
            if v not in hits:
                continue
            c = v.casefold()
            how = "whole value" if c in values else "token" if c in tokens else "substring"
            has = bool(re.search(r"file[-_][A-Za-z0-9]{10,}|[0-9a-f]{8}-", v))
            print(f"  {f}: len {len(v)} contains-id {has} shape {re.sub(r'[0-9a-f]', 'x', re.sub(r'[g-zG-Z]', 'a', v))[:40]} | matched as {how}")
