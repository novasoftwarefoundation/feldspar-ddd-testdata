"""Probe the ChatGPT error-case zips. Masked contexts, key names, shapes and counts only.

    python3 cg_probe.py <zip> [<zip> ...]
"""
import collections
import sys
import json
import re
import zipfile

mask = lambda s: re.sub(r"[^\W\d_]", "a", re.sub(r"\d", "9", s))
files = sorted(sys.argv[1:])
convs = {}
for p in files:
    raw = zipfile.ZipFile(p).read("conversations.json").decode("utf-8", "replace")
    try:
        convs[p] = json.loads(raw)
        print(p[:26], "conversations.json parses: list of", len(convs[p]))
    except json.JSONDecodeError as e:
        print(p[:26], "conversations.json does NOT parse:", e.msg, "at char", e.pos, "of", len(raw),
              "| masked context:", repr(mask(raw[max(0, e.pos - 40):e.pos + 40])))
z = zipfile.ZipFile(files[0])
print("\nattachment types:", collections.Counter(
    ("jpg" if d[:3] == b"\xff\xd8\xff" else "png" if d[:4] == b"\x89PNG" else "webp" if d[8:12] == b"WEBP" else
     "pdf" if d[:4] == b"%PDF" else "zip(docx/xlsx?)" if d[:2] == b"PK" else "gif" if d[:3] == b"GIF" else "?" + d[:4].hex())
    for d in (z.read(i) for i in z.infolist() if i.filename.endswith(".dat"))))
for name in ("user.json", "user_settings.json", "library_files.json", "conversation_asset_file_names.json",
             "export_manifest.json", "ads.json"):
    d = json.loads(z.read(name))
    keys = collections.Counter()
    def walk(n, p):
        if isinstance(n, dict):
            for k, v in n.items():
                kk = k if re.fullmatch(r"[a-z_A-Z]+", k) else "<datakey:" + mask(k)[:20] + ">"
                walk(v, p + "." + kk)
        elif isinstance(n, list):
            for x in n:
                walk(x, p + "[]")
        else:
            s = "str" if isinstance(n, str) else type(n).__name__
            if isinstance(n, str):
                s = "empty" if not n else "url" if n.startswith("http") else "email" if re.fullmatch(r"\S+@\S+", n) else \
                    "uuid" if re.fullmatch(r"[0-9a-f-]{36}", n) else "file-id" if re.match(r"file[-_]", n) else "text%d" % len(n)
            keys[p + " " + s] += 1
    walk(d, "$")
    print("\n##", name)
    for k, n in keys.most_common(25):
        print("  ", n, k)
h = z.read("chat.html").decode("utf-8", "replace")
print("\nchat.html: script tags", len(re.findall(r"<script", h)), "| 'var jsonData' present:", "jsonData" in h,
      "| assetsJson present:", "assetsJson" in h, "| emails:", len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", h)))
m = re.search(r"var jsonData = (\[.*?\]);\n", h, re.S)
if m:
    try:
        jd = json.loads(m.group(1))
        print("   embedded jsonData parses: list of", len(jd))
    except json.JSONDecodeError as e:
        print("   embedded jsonData does not parse:", e.msg)
