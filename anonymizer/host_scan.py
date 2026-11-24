"""Scan zips for URLs whose host is written with capitals and is not a platform host the tools keep on purpose.
With the old URL code such a host was never replaced, so in a copy made by an old tool it is the real host.
Counts only, never a host.   python3 host_scan.py <zip> [...]"""
import re, sys, zipfile, io
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import anonymize as an
import takeout, tiktok_anon, cg_anon
KEEP = [an.META_HOSTS, takeout.KEEP_HOSTS, tiktok_anon.TT_HOSTS, cg_anon.OPENAI_HOSTS]
URL = re.compile(rb"https?:(?:\\?/){2}([^/\s\"'\\?#<>:)]+)", re.I)
TEXT = (".json", ".html", ".htm", ".txt", ".csv", ".srt", ".js", ".xml", ".ics", ".vcf", ".mbox")

def scan(z, out):
    for i in z.infolist():
        name = i.filename.lower()
        if name.endswith(".zip"):
            with z.open(i) as f:
                scan(zipfile.ZipFile(io.BytesIO(f.read())), out)
        elif name.endswith(TEXT):
            with z.open(i) as f:
                tail = b""
                while True:
                    chunk = f.read(64 << 20)
                    if not chunk:
                        break
                    buf = tail + chunk
                    for m in URL.finditer(buf):
                        h = m.group(1)
                        if h != h.lower():
                            hs = h.decode("latin1").lower()
                            if not any(k.search(hs) for k in KEEP):
                                out["urls"] += 1; out["hosts"].add(hs)
                    tail = buf[-300:]
            out["text_entries"] += 1
for p in sys.argv[1:]:
    out = {"urls": 0, "hosts": set(), "text_entries": 0}
    scan(zipfile.ZipFile(p), out)
    print(f"{p.rsplit('/', 1)[-1]}: capitalised non-platform hosts: {out['urls']} URLs, {len(out['hosts'])} distinct"
          f" ({out['text_entries']} text entries)")
