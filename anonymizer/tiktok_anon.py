"""Anonymize a TikTok JSON export (user_data.json in a zip), keeping its structure and byte format.

    python3 tiktok_anon.py <original.zip> <output.zip>

Rules are by field name (TikTok's own keys). Same zip entries; JSON written back as TikTok writes it
(indent 2, raw UTF-8, the original's trailing newlines). Prints only counts, never a value.
"""
import collections
import json
import os
import re
import sys
import zipfile
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(__file__))
import anonymize as an  # noqa: E402

STATS = collections.Counter()
KEEP = {"Date", "TimeStamp", "CommentTime", "WatchTime", "RawTime", "SharedContent", "Method", "Event", "DeviceModel",
        "DeviceSystem", "NetworkType", "Carrier", "Resolution", "App Version", "LastRegion", "Platform", "likesReceived",
        "Type", "Photo", "MostRecentModificationTimeInApp", "MostRecentModificationTimeInWeb", "IsFastLane"}
ACTION = {"UserName": "username", "userName": "username", "From": "username", "Name": "username",
          "IP": "ip", "IDFA": "id", "IDFV": "id", "GAID": "id", "Android ID": "id", "Web ID": "id",
          "SearchTerm": "text", "Comment": "text", "CommentContent": "text", "Content": "text", "HashtagName": "text",
          "Source": "text", "AdInterestCategories": "text", "bioDescription": "text", "Description": "text",
          "Link": "url", "HashtagLink": "url", "profilePhoto": "url", "profileVideo": "url", "Profile Photo": "url",
          "telephoneNumber": "phone", "PhoneNumber": "phone", "emailAddress": "email", "Email": "email",
          "birthDate": "dob", "GpsData": "gps", "FirstName": "name", "LastName": "name", "Address": "text",
          "ZipCode": "id", "Unit": "text", "City": "city", "State": "region", "Country": "country"}
NA = {"", "N/A", "None", "null"}
TT_HOSTS = re.compile(r"(^|\.)(tiktok\.com|tiktokv\.com|tiktokcdn\.com|tiktokcdn-[\w-]+\.com|byteoversea\.com|ibyteimg\.com)$")
TT_STRUCT = {"", "share", "video", "user", "tag", "music", "@", "live", "obj", "tos-maliva-avt-0068", "photo"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def tt_url(u):
    try:
        p = urlsplit(u)
    except ValueError:
        return an.scramble_ident(u, "url")
    host = p.hostname or ""
    netloc = p.netloc if TT_HOSTS.search(host) or not host else an.fake_netloc(p.netloc, host)
    segs = [s if s in TT_STRUCT else ("@" + an.fake_username(s[1:]) if s.startswith("@") else an.scramble_ident(s, "tt-id"))
            for s in p.path.split("/")]
    query = "&".join((kv.split("=", 1)[0] + "=" + an.scramble_ident(kv.split("=", 1)[1], "q")) if "=" in kv else kv
                     for kv in p.query.split("&")) if p.query else ""
    return urlunsplit((p.scheme, netloc, "/".join(segs), query, an.scramble_ident(p.fragment, "f") if p.fragment else ""))


an.fake_url = tt_url


def fake_dob(v):
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", v)
    r = an.rng_for("dob", v)
    if m:
        return f"{1 + r.randrange(28):0{len(m.group(1))}d}-{r.choice(MONTHS)}-{1985 + r.randrange(15)}"
    return an.fake_dob(v)


def fake_gps(v):
    def num(m, axis=[0]):
        axis[0] ^= 1
        return an.fake_coord(m.group(), 1 - axis[0])
    return re.sub(r"-?\d+\.\d+", num, v)


def value(v, key):
    if not isinstance(v, str) or v in NA:
        return v
    if key in KEEP:
        STATS[("keep", key)] += 1
        return v
    act = ACTION.get(key)
    if act is None:
        STATS[("unknown key, kept (settings)", key)] += 1
        return v
    STATS[(act, key)] += 1
    if act == "dob":
        return fake_dob(v)
    if act == "gps":
        return fake_gps(v)
    if act == "url" and not re.match(r"https?://", v):
        act = "text"
    if act == "text" and re.match(r"https?://\S+$", v):
        act = "url"
    return an.apply(act, v, key)


def walk(n, key=None, path=""):
    if isinstance(n, dict):
        out = {}
        for k, v in n.items():
            nk = k
            if path.endswith("ChatHistory") and k.startswith("Chat History with "):
                user = k[len("Chat History with "):].rstrip(":")
                nk = "Chat History with " + an.apply("username", user, "chat key") + k[len("Chat History with ") + len(user):]
                STATS[("username", "chat key")] += 1
            elif k in an.USERNAMES:
                nk = an.apply("username", k, "username as key")
                STATS[("username", "username as key")] += 1
            elif path.endswith("WatchLiveMap") and k.isdigit():
                nk = an.apply("id", k, "live room key")
                STATS[("id", "live room key")] += 1
            out[nk] = walk(v, k, path + "." + k)
        return out
    if isinstance(n, list):
        if path.endswith("Settings.SettingsMap.Content Preferences.Video Languages Preferences"):
            return n
        return [walk(x, key, path) for x in n]
    return value(n, key)


def collect(n, key=None):
    if isinstance(n, dict):
        for k, v in n.items():
            if k.startswith("Chat History with "):
                an.USERNAMES.add(k[len("Chat History with "):].rstrip(":"))
            collect(v, k)
    elif isinstance(n, list):
        for x in n:
            collect(x, key)
    elif isinstance(n, str) and n not in NA:
        if ACTION.get(key) == "username":
            an.USERNAMES.add(n)


def main(src, dst):
    zin = zipfile.ZipFile(src)
    files = collections.Counter()
    with zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            raw = zin.read(info)
            if info.filename.endswith(".json"):
                text = raw.decode("utf-8")
                data = json.loads(text)
                collect(data)
                an._all_strings(data)
                for k in list(an.USERNAMES):
                    an.ORIGINALS_CF.add(k.casefold())
                taken = {w.casefold() for x in an.USERNAMES for w in re.findall(r"[^\W\d_]+", x)}
                for n in list(an.BY_LEN):
                    an.BY_LEN[n] = [w for w in an.BY_LEN[n] if w.casefold() not in taken] or an.BY_LEN[n]
                body = json.dumps(walk(data), indent=2, ensure_ascii=False)
                body += text[len(text.rstrip("\n")):]          # the original's trailing newlines
                if json.dumps(data, indent=2, ensure_ascii=False) + text[len(text.rstrip("\n")):] != text:
                    raise SystemExit("unknown JSON byte format; stopping")
                body = body.encode("utf-8")
                files["json"] += 1
            else:
                raise SystemExit("unexpected entry type; stopping")
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.create_system = info.create_system
            zout.writestr(zi, body)
    print("files:", dict(files), "| known usernames:", len(an.USERNAMES))
    for (k, f), n in sorted(STATS.items()):
        print(f"   {k} | {f}: {n}")
    print("fake collisions:", dict(an.COLLISIONS) or "none")


if __name__ == "__main__":
    main(*sys.argv[1:3])
