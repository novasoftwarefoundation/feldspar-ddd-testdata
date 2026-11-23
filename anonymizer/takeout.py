"""Anonymize a Google Takeout zip (My Activity / YouTube JSON, YouTube CSVs, archive_browser.html).

    python3 takeout.py <original.zip> <output.zip>

Same entries in the same order (folders, compression, dates), every JSON file written back in the byte
format it came in (see gjson.py), CSVs in their own dialect. Google's template words in titles
("Je hebt naar … gekeken", "Je hebt gezocht naar …") are kept; the personal part is faked.
Prints only counts, never a value.
"""
import collections
import csv
import io
import json
import os
import re
import sys
import zipfile
from urllib.parse import quote, unquote, urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(__file__))
import anonymize as an  # noqa: E402
import gjson  # noqa: E402

STATS = collections.Counter()
TEMPLATES = [("Je hebt naar ", " gekeken"), ("Je hebt gezocht naar ", ""), ("Afbeelding bekeken van ", ""),
             ("Je hebt ", " bezocht"), ("Je hebt ", " bekeken"), ("Je hebt ", " gebruikt"), ("Je hebt ", " gelezen"),
             ("Watched ", ""), ("Searched for ", ""), ("Visited ", ""), ("Viewed ", ""), ("Je hebt ", "")]
KEEP_HOSTS = re.compile(r"(^|\.)(youtube\.com|youtu\.be|google\.[a-z.]+|googleusercontent\.com|ytimg\.com|gstatic\.com|"
                        r"googleapis\.com|youtube-nocookie\.com|w3\.org)$")
STRUCT = {"", "watch", "results", "channel", "user", "c", "shorts", "playlist", "search", "url", "maps", "place",
          "imgres", "news", "articles", "read", "topics", "stories", "vi", "vi_webp", "hqdefault.jpg", "mqdefault.jpg",
          "sddefault.jpg", "maxresdefault.jpg", "default.jpg", "hq720.jpg", "embed", "live", "post", "feed", "history",
          "@", "dir", "data", "intl", "nl", "en", "publications", "sections", "rss", "s", "amp", "img", "images"}


def ident(x):
    """Video, channel, comment ids: same shape, new characters; the same id maps the same way everywhere."""
    if re.fullmatch(r"UC[\w-]{22}", x):
        return "UC" + an.scramble_ident(x[2:], "yt-id")
    return an.scramble_ident(x, "yt-id")


def fake_host(h):
    labels = h.split(".")
    return ".".join(lab if lab == "www" or i == len(labels) - 1 else an.scramble_ident(lab, "host")
                    for i, lab in enumerate(labels))


def g_fake_url(u):
    try:
        p = urlsplit(u)
    except ValueError:
        return an.scramble_ident(u, "url")
    host = p.hostname or ""
    netloc = p.netloc if KEEP_HOSTS.search(host) or not host else p.netloc.replace(host, fake_host(host))
    segs = []
    for s in p.path.split("/"):
        if s in STRUCT:
            segs.append(s)
        elif s.startswith("@"):
            segs.append("@" + an.scramble_ident(s[1:], "handle"))
        else:
            segs.append(ident(s))
    query = []
    if p.query:
        for kv in p.query.split("&"):
            k, eq, v = kv.partition("=")
            if not eq:
                query.append(ident(k))
            elif v.startswith(("http://", "https://")):
                query.append(k + "=" + g_fake_url(v))
            elif v.lower().startswith(("http%3a", "https%3a")):
                query.append(k + "=" + quote(g_fake_url(unquote(v)), safe=""))
            else:
                query.append(k + "=" + ident(v))
    frag = an.scramble_ident(p.fragment, "frag") if p.fragment else ""
    return urlunsplit((p.scheme, netloc, "/".join(segs), "&".join(query), frag)) + ("?" if u.endswith("?") and not p.query else "")


an.fake_url = g_fake_url          # free text with links in it uses the Google-aware URL faker


def text(v, field):
    STATS[("text", field)] += 1
    return an.apply("text", v, field)


def fake_title(t):
    for pre, suf in TEMPLATES:
        if t.startswith(pre) and t.endswith(suf) and len(t) > len(pre) + len(suf):
            mid = t[len(pre):len(t) - len(suf)]
            STATS[("title template", pre + "…" + suf)] += 1
            new = an.apply("url", mid, "title") if re.match(r"https?://", mid) else text(mid, "title")
            return pre + new + suf
    STATS[("title template", "none")] += 1
    return text(t, "title")


def fake_record(r):
    out = {}
    for k, v in r.items():
        if k == "header":
            own = "." not in v or KEEP_HOSTS.search(v.lower())
            out[k] = v if own else an.apply("header", v, k)
            STATS[("header", "product name or Google domain kept" if own else "domain")] += 1
        elif k == "title":
            out[k] = fake_title(v)
        elif k == "titleUrl":
            out[k] = an.apply("url", v, k)
        elif k == "time" or k in ("products", "activityControls"):
            out[k] = v
            STATS[("kept", k)] += 1
        elif k in ("subtitles", "details", "locationInfos"):
            new = []
            for x in v:
                y = {}
                for kk, vv in x.items():
                    if kk == "url":
                        y[kk] = an.apply("url", vv, k + ".url")
                    else:
                        y[kk] = text(vv, k + "." + kk)
                new.append(y)
            out[k] = new
        else:
            STATS[("unknown key, replaced as text", k)] += 1
            out[k] = json.loads(json.dumps(v)) if not isinstance(v, str) else text(v, k)
    return out


CSV_COLUMNS = {
    "Kanaal-ID": "id", "Channel Id": "id", "Channel ID": "id", "Kanaal-URL": "url", "Channel Url": "url",
    "Kanaaltitel": "text", "Channel Title": "text", "Comment ID": "id", "Parent comment ID": "id", "Video ID": "id",
    "Comment create timestamp": "keep", "Price": "keep", "Comment text": "segments", "Reactietekst": "segments",
}


def fake_csv(raw):
    rows = list(csv.reader(io.StringIO(raw)))
    head = rows[0]
    for row in rows[1:]:
        for c, cell in enumerate(row):
            kind = CSV_COLUMNS.get(head[c], "text")
            if cell == "" or kind == "keep":
                continue
            if kind == "id":
                row[c] = an.apply("csv-id", cell, head[c])
            elif kind == "url":
                row[c] = an.apply("url", cell, head[c])
            elif kind == "segments":
                try:
                    segs = json.loads(f"[{cell}]")
                    for s in segs:
                        if isinstance(s, dict) and isinstance(s.get("text"), str):
                            s["text"] = text(s["text"], "comment text")
                    row[c] = ",".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in segs)
                except ValueError:
                    row[c] = text(cell, "comment text")
            else:
                row[c] = text(cell, head[c])
            STATS[("csv " + kind, head[c])] += 1
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    out = buf.getvalue()
    return out if raw.endswith("\n") else out.rstrip("\n")


def fake_html(t):
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", lambda m: (STATS.update([("html", "email")]), an.apply("email", m.group(), "html email"))[1], t)
    t = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
               lambda m: (STATS.update([("html", "archive id")]), an.scramble_ident(m.group(), "uuid"))[1], t)
    return t


def main(src, dst):
    zin = zipfile.ZipFile(src)
    # channel names: the fake-word pool must never spell one by chance
    for i in zin.infolist():
        if i.filename.endswith(".json"):
            for r in json.loads(zin.read(i)):
                an.NAMES.update(s.get("name", "") for s in r.get("subtitles", []))
        elif i.filename.endswith(".csv"):
            rows = list(csv.reader(io.StringIO(zin.read(i).decode("utf-8"))))
            for c, h in enumerate(rows[0] if rows else []):
                if CSV_COLUMNS.get(h) == "text":
                    an.NAMES.update(r[c] for r in rows[1:] if len(r) > c)
    an.NAMES.discard("")
    for i in zin.infolist():           # every original string: a fake must never equal one
        if i.filename.endswith(".json"):
            data = json.loads(zin.read(i))
            an._all_strings(data)
            for r in data:                 # the personal part of a template title counts as an original too
                t = r.get("title", "")
                for pre, suf in TEMPLATES:
                    if t.startswith(pre) and t.endswith(suf) and len(t) > len(pre) + len(suf):
                        mid = t[len(pre):len(t) - len(suf)].casefold()
                        an.ORIGINALS_CF.add(mid)
                        if 6 <= len(mid) <= 30:
                            an.ORIG_SUBS.add(mid)
                        break
        elif i.filename.endswith(".csv"):
            for row in csv.reader(io.StringIO(zin.read(i).decode("utf-8"))):
                an.ORIGINALS_CF.update(c.casefold() for c in row if c)
                for c in row:
                    t = an.tokens_of(c)
                    an.ORIG_TOKENS.update(t)
                    an.ORIG_SUBS.update(w for w in t if 6 <= len(w) <= 30)
                    if 6 <= len(c) <= 30:
                        an.ORIG_SUBS.add(c.casefold())
    taken = {w.casefold() for x in an.NAMES for w in re.findall(r"[^\W\d_]+", x)}
    for i in zin.infolist():           # nor any word of an original title (search terms, video titles)
        if i.filename.endswith(".json"):
            for r in json.loads(zin.read(i)):
                taken.update(w.casefold() for w in re.findall(r"[^\W\d_]{4,}", r.get("title", "")))
    for n in list(an.BY_LEN):
        an.BY_LEN[n] = [w for w in an.BY_LEN[n] if w.casefold() not in taken]
        if not an.BY_LEN[n]:
            del an.BY_LEN[n]
    print("channel names:", len(an.NAMES), "| fake-word pool:", sum(map(len, an.BY_LEN.values())))
    files = collections.Counter()
    with zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            if info.is_dir():
                body = b""
                files["dir"] += 1
            elif info.filename.endswith(".json"):
                raw = zin.read(info)
                fmt = gjson.pick(raw)
                if fmt is None:
                    raise SystemExit("unknown JSON format in a file; stopping")
                body = gjson.dumps([fake_record(r) for r in json.loads(raw)], *fmt).encode("utf-8")
                files["json " + fmt[0]] += 1
            elif info.filename.endswith(".csv"):
                body = fake_csv(zin.read(info).decode("utf-8")).encode("utf-8")
                files["csv"] += 1
            elif info.filename.endswith(".html"):
                body = fake_html(zin.read(info).decode("utf-8")).encode("utf-8")
                files["html"] += 1
            else:
                raise SystemExit("unexpected file type; stopping")
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.create_system = info.create_system
            zout.writestr(zi, body)
    print("files:", dict(files))
    for (kind, field), n in sorted(STATS.items()):
        print(f"   {kind} | {field}: {n}")
    print("fake collisions:", dict(an.COLLISIONS) or "none")


if __name__ == "__main__":
    main(*sys.argv[1:3])
