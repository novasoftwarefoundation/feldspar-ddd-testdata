"""Survey a Google Takeout zip: file names (digits masked), JSON key paths with value shapes, CSV headers
and column shapes, HTML size and tag counts. Never prints values (CSV headers are Google's column names)."""
import collections
import csv
import io
import json
import re
import sys
import zipfile


def shape(v):
    if not isinstance(v, str):
        return type(v).__name__
    if v == "":
        return "empty"
    if re.match(r"https?://", v):
        return "url"
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return "num"
    if re.fullmatch(r"\S+@\S+\.\S+", v):
        return "email"
    if re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", v):
        return "iso-time"
    if re.fullmatch(r"UC[\w-]{22}", v):
        return "yt-channel-id"
    return "text"


z = zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    if i.is_dir():
        continue
    name = re.sub(r"\d", "9", i.filename)
    d = z.read(i)
    print("##", name, len(d), "bytes", "deflate" if i.compress_type == 8 else "stored")
    if i.filename.endswith(".json"):
        data = json.loads(d)
        keys = collections.defaultdict(collections.Counter)

        def walk(n, p):
            if isinstance(n, dict):
                for k, v in n.items():
                    walk(v, p + "." + k)
            elif isinstance(n, list):
                if not n:
                    keys[p + "[]"]["EMPTY"] += 1
                for x in n:
                    walk(x, p + "[]")
            else:
                keys[p][shape(n)] += 1

        walk(data, "$")
        for k, c in keys.items():
            print("   ", k, dict(c))
        print("    top-level length:", len(data) if isinstance(data, (list, dict)) else "-",
              "| raw starts:", re.sub(rb'"(?:[^"\\]|\\.)*"', b'"S"', d[:80]))
    elif i.filename.endswith(".csv"):
        text = d.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        print("    header:", rows[0] if rows else None, "| rows:", len(rows) - 1, "| bom:", d[:3] == b"\xef\xbb\xbf",
              "| line ending:", "CRLF" if b"\r\n" in d else "LF")
        for ci in range(len(rows[0]) if rows else 0):
            print("     col", ci, dict(collections.Counter(shape(r[ci]) for r in rows[1:] if len(r) > ci)))
    elif i.filename.endswith(".html"):
        t = d.decode("utf-8", "replace")
        print("    tags:", dict(collections.Counter(re.findall(r"<(\w+)", t)).most_common(12)),
              "| emails:", len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)), "| has <script>:", "<script" in t)
