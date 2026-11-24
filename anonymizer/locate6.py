"""verify2's leak hits (4+ chars), one line per distinct value: why it occurs in replacement text (a kept
top-level domain, a kept Meta host, a query key, carried over from its own original, a pool fake, new text).
Categories and field names only, never values.

    python3 locate6.py <original.zip> <copy.zip>
"""
import collections, re, sys, zipfile
from urllib.parse import urlsplit
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import verify2_core as vc  # noqa: E402
import anonymize as an  # noqa: E402

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
pairs = vc.pairs(orig, copy)
for a, b in zip(orig.infolist(), copy.infolist()):          # srt captions and renamed path parts count as replaced
    if a.filename.endswith(".srt"):
        for x, y in zip(orig.read(a).decode().split("\n"), copy.read(b).decode().split("\n")):
            pairs.append(("srt", x.strip(), y))
replaced = collections.defaultdict(set)
for f, a, b in pairs:
    if a != b and a:
        replaced[a.casefold()].add(f.split(".json")[0])
derived = [(f, a, b) for f, a, b in pairs if a != b]
TOKS = lambda s: set(re.findall(r"[^\s\"',;:!?()\[\]{}<>]+", s)) | set(re.findall(r"[\w.@+\-]+", s))
pool = {w.casefold() for ws in an.BY_LEN.values() for w in ws} | {w.casefold() for w in an.FIRST + an.LAST + an.CITIES + an.REGIONS + an.COUNTRIES}
dtok = [TOKS(b.casefold()) for f, a, b in derived]
dleaf = {b.casefold() for f, a, b in derived}
alltok = set().union(*dtok)
dcorpus = "\n".join(b.casefold() for f, a, b in derived)
for v, vf in sorted(replaced.items(), key=lambda x: len(x[0])):
    if len(v) < 4 or not (v in dleaf or v in alltok or (len(v) >= 6 and v in dcorpus)):
        continue
    why = collections.Counter()
    for (f, a, b), tk in zip(derived, dtok):
        bc, ac = b.casefold(), a.casefold()
        if not (v == bc or v in tk or (len(v) >= 6 and v in bc)):
            continue
        cat = []
        if re.match(r"https?://", bc):
            ua, ub = urlsplit(ac), urlsplit(bc)
            hl = (ub.hostname or "").split(".")
            if v == hl[-1]: cat.append("url: top-level domain (kept)")
            elif v in (ub.hostname or "") and ub.hostname == ua.hostname: cat.append("url: host kept (Meta host)")
            elif any(v == kv.split("=")[0] for kv in ub.query.split("&")): cat.append("url: query key name (kept)")
            elif any(v == s for s in ub.path.split("/") if s in an.STRUCT): cat.append("url: Meta path word (kept)")
            else: cat.append("url: other")
        elif v in ac and v not in (set(TOKS(bc)) - set(TOKS(ac))):
            cat.append("carried over unchanged from that value's original")
        elif v in pool or any(v in TOKS(w) for w in pool):
            cat.append("fake drawn from a pool equals it")
        else:
            cat.append("new text")
        why[(f.split(".json")[0], *cat)] += 1
    if why:
        print(f"len {len(v)} | original fields: {sorted(vf)[:3]} | meta word: {v in an.META_WORDS} | in copy as:", dict(why))
