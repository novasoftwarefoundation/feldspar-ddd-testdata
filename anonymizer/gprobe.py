"""Probes for a Google Takeout zip. Prints counts and booleans only (template strings are mine)."""
import collections
import csv
import io
import json
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
TEMPLATES = [("Je hebt gezocht naar ", ""), ("Je hebt ", " bekeken"), ("Je hebt ", " bezocht"), ("Je hebt ", " gebruikt"),
             ("Je hebt ", " gelezen"), ("Je hebt ", " opgeslagen"), ("Je hebt ", " beluisterd"), ("Je hebt ", " gezien"),
             ("Afbeelding bekeken van ", ""), ("Gezocht naar ", ""), ("Bekeken: ", ""), ("Je hebt ", "")]
PRODUCTS = {"YouTube", "YouTube Music", "Zoeken", "Google Zoeken", "Chrome", "Discover", "Nieuws", "Google Nieuws",
            "Advertenties", "Afbeeldingen zoeken", "Video's zoeken", "Video’s zoeken", "Google Ads", "Maps", "Afbeeldingen",
            "Video_s zoeken", "Google Afbeeldingen", "Google Play Store"}


def dumps_google(o, ind=0):
    """Google Takeout style: '[{' / '},{' joins for lists of objects, inline lists of scalars."""
    pad = "  " * ind
    if isinstance(o, dict):
        items = [pad + "  " + json.dumps(k, ensure_ascii=False) + ": " + dumps_google(v, ind + 1) for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o):
            return "[" + ",".join(dumps_google(x, ind) for x in o) + "]"
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in o) + "]"
    return json.dumps(o, ensure_ascii=False)


for i in z.infolist():
    if i.is_dir():
        continue
    fn = re.sub(r"\d", "9", i.filename)
    d = z.read(i)
    if i.filename.endswith(".json"):
        data = json.loads(d)
        t = collections.Counter()
        for rec in data:
            title = rec.get("title", "")
            for p, s in TEMPLATES:
                if title.startswith(p) and title.endswith(s) and len(title) > len(p) + len(s):
                    t[repr((p, s))] += 1
                    break
            else:
                t["no template"] += 1
        heads = collections.Counter(rec.get("header") for rec in data)
        prods = collections.Counter(p for rec in data for p in rec.get("products", []))
        ctrls = collections.Counter(c for rec in data for c in rec.get("activityControls", []))
        det = collections.Counter(x.get("name") for rec in data for x in rec.get("details", []))
        src = collections.Counter(x.get("source") for rec in data for x in rec.get("locationInfos", []))
        lname = collections.Counter(x.get("name") for rec in data for x in rec.get("locationInfos", []))
        print("##", fn, "| records", len(data))
        print("   title templates:", dict(t))
        print("   headers: distinct", len(heads), "all known products:", all(h in PRODUCTS for h in heads),
              "| products: distinct", len(prods), "all known:", all(p in PRODUCTS for p in prods))
        print("   activityControls distinct", len(ctrls), "| details.name distinct", len(det), "of", sum(det.values()),
              "| location name distinct", len(lname), "of", sum(lname.values()), "| location source distinct", len(src))
        cands = {"indent2": json.dumps(data, indent=2, ensure_ascii=False), "indent2-ascii": json.dumps(data, indent=2),
                 "google": dumps_google(data)}
        print("   serializer matches:", {k: v.encode() == d for k, v in cands.items()},
              "| trailing newline:", d.endswith(b"\n"), "| non-ascii raw:", any(c > 127 for c in d))
    elif i.filename.endswith(".csv"):
        text = d.decode("utf-8")
        rows = list(csv.reader(io.StringIO(text)))
        for term in ("\n", "\r\n"):
            buf = io.StringIO()
            csv.writer(buf, lineterminator=term).writerows(rows)
            print("##", fn, "| csv round-trip with", repr(term), ":", buf.getvalue() == text)
        if "reacties" in i.filename:
            ok = 0
            for r in rows[1:]:
                raw = r[6]
                try:
                    segs = json.loads(f"[{raw}]")
                    ok += ",".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in segs) == raw
                except Exception:
                    pass
            print("   comment text segments round-trip:", ok, "of", len(rows) - 1)
    elif i.filename.endswith(".html"):
        t = d.decode("utf-8")
        srcs = re.findall(r'<img[^>]*src="([^"]*)"', t)
        print("##", fn, "| img src kinds:", dict(collections.Counter("data:" + s[5:20].split(";")[0] if s.startswith("data:") else
                                                                       "http" if s.startswith("http") else "other" for s in srcs)),
              "| data-uri sizes:", sorted(len(s) for s in srcs if s.startswith("data:"))[-3:])
        print("   emails:", len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)), "| text nodes:", len(re.findall(r">([^<>]*\S[^<>]*)<", t)))
