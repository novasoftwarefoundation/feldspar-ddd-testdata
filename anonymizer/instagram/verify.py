"""Compare an original export and its anonymized copy. Prints counts only, never a value.

    python3 verify.py <original.zip> <copy.zip> [--username NAME] [--email ADDRESS] ...

1. Structure: same number and order of entries, same names (thread folders aside), same JSON keys,
   nesting, list lengths and value types; string kinds (empty / URL / other) unchanged.
2. Leak scan: the account's username, name, emails and every value of personal_information.json,
   plus every username, name, email, phone number and IP address in the original, searched in
   the copy (entry names and decoded JSON text).
"""
import collections
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
import anonymize as an  # noqa: E402  (reuses its username/name collector, no values printed)

orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
# Extra values to search for: the account's username and emails as the participant gave them.
given = {"--username": [], "--email": []}
for flag, value in zip(sys.argv[3::2], sys.argv[4::2]):
    given[flag].append(value)
oi, ci = orig.infolist(), copy.infolist()


def fix(s):
    return an.unmoji(s)[0]


def kind(v):
    if isinstance(v, str):
        return "empty" if v == "" else "url" if re.match(r"https?://", v) else "str"
    return type(v).__name__


diff = collections.Counter()


def compare(a, b, path):
    if type(a) is not type(b):
        diff["type"] += 1
        return
    if isinstance(a, dict):
        if list(a.keys()) != list(b.keys()):
            diff["keys"] += 1
        for k in a:
            if k in b:
                compare(a[k], b[k], path + "." + k)
    elif isinstance(a, list):
        if len(a) != len(b):
            diff["list_length"] += 1
        for x, y in zip(a, b):
            compare(x, y, path + "[]")
    elif kind(a) != kind(b):
        diff["string_kind:" + kind(a) + "->" + kind(b)] += 1


def mask(n):
    return re.sub(r"/\d{10,}(\.\w+)?$", r"/<id>\1", re.sub(r"(inbox|message_requests)/[^/]+", "T", n))


print("entries:", len(oi), "->", len(ci))
same_names = renamed = other = 0
for a, b in zip(oi, ci):
    if a.filename == b.filename:
        same_names += 1
    elif mask(a.filename) == mask(b.filename):
        renamed += 1
    else:
        other += 1
    if a.filename.endswith(".json"):
        compare(json.loads(orig.read(a)), json.loads(copy.read(b)), "$")
    else:
        da, db = orig.read(a), copy.read(b)
        sig = lambda d: "jpg" if d[:3] == b"\xff\xd8\xff" else "png" if d[:4] == b"\x89PNG" else ("mp4" + ("v" if b"vide" in d else "") + ("a" if b"soun" in d else "")) if d[4:8] == b"ftyp" else "?"
        if sig(da) != sig(db):
            diff["media_type"] += 1
        diff["media_bytes_identical"] += da == db
print("names identical:", same_names, "| thread folder or media id renamed only:", renamed, "| other name changes:", other)
print("structure differences:", dict(diff) or "none")

# --- leak scan ---------------------------------------------------------------------------------
strings_o = []


def strings(n, out):
    if isinstance(n, dict):
        for k, v in n.items():
            out.append(fix(k))
            strings(v, out)
    elif isinstance(n, list):
        for x in n:
            strings(x, out)
    elif isinstance(n, str):
        out.append(fix(n))


for a in oi:
    if a.filename.endswith(".json"):
        d = json.loads(orig.read(a))
        an.collect(d)
        strings(d, strings_o)
corpus_parts = [b.filename for b in ci]
for b in ci:
    if b.filename.endswith(".json"):
        raw = copy.read(b).decode("ascii")
        corpus_parts.append(raw)
        strings(json.loads(raw), corpus_parts)
corpus = "\n".join(corpus_parts).casefold()
tokens = set(re.findall(r"[\w.@+\-:]+", corpus))

pi = json.loads(orig.read("personal_information/personal_information/personal_information.json"))["profile_user"][0]
own = {}
own["username (given)"] = given["--username"]
own["username (export)"] = [fix(pi["string_map_data"]["Username"]["value"])]
name = fix(pi["string_map_data"]["Name"]["value"])
own["name"] = [name]
own["name parts"] = [p for p in name.split() if len(p) >= 3]
emails = sorted({s for s in strings_o if an.EMAIL_RE.match(s)})
own_email_files = ("autofill_information.json", "profile_activity.json", "checkout_payment_information.json",
                   "instagram_profile_information.json", "information_you've_submitted_to_advertisers.json")
own_emails = set()
for a in oi:
    if a.filename.endswith(own_email_files):
        tmp = []
        strings(json.loads(orig.read(a)), tmp)
        own_emails.update(s for s in tmp if an.EMAIL_RE.match(s))
own["account emails"] = sorted(own_emails | set(given["--email"]))
pi_values = []
strings({k: v for k, v in pi.items()}, pi_values)
labels = set(pi["string_map_data"].keys()) | {"string_map_data", "media_map_data", "title", "href", "value", "timestamp",
                                              "uri", "creation_timestamp", "media_metadata", "camera_metadata",
                                              "has_camera_metadata", "cross_post_source", "source_app", "Profile Photo"}
own["personal_information.json values"] = sorted({v for v in pi_values if v and v not in labels and fix(v) not in labels})

print("\nleak scan of the copy (substring, case-insensitive):")
for field, vals in own.items():
    hits = sum(1 for v in vals if v.casefold() in corpus)
    print(f"  {field}: {len(vals)} value(s), {hits} found")
# which personal_information.json fields were found (field names only)
found_fields = []
for k, e in pi["string_map_data"].items():
    v = fix(e.get("value", ""))
    if v and v.casefold() in corpus:
        found_fields.append(k)
for k, e in pi.get("media_map_data", {}).items():
    for kk in ("uri", "title"):
        v = e.get(kk)
        if isinstance(v, str) and v and v.casefold() in corpus:
            found_fields.append(f"{k}.{kk}")
        cps = e.get("cross_post_source", {}).get("source_app")
    if isinstance(cps, str) and cps.casefold() in corpus:
        found_fields.append(f"{k}.cross_post_source.source_app")
if isinstance(pi.get("title"), str) and pi["title"] and fix(pi["title"]).casefold() in corpus:
    found_fields.append("title")
print("  personal_information.json fields whose value occurs in the copy:", found_fields or "none")
def whole_word(v):
    return re.search(r"(?<![\w.])" + re.escape(v.casefold()) + r"(?![\w])", corpus) is not None
for k, e in pi["string_map_data"].items():
    v = fix(e.get("value", ""))
    if v and v.casefold() in corpus:
        print(f"    {k}: as a whole word: {whole_word(v)}; equal to an original leaf elsewhere too: "
              f"{sum(1 for x in strings_o if x == v) - 1} other(s)")

media_ids = {re.sub(r"\.\w+$", "", a.filename.rsplit("/", 1)[-1]) for a in oi if not a.filename.endswith(".json")}
print(f"  media file ids: {len(media_ids)} distinct, {sum(1 for m in media_ids if m in corpus)} found")
print("\nall identities in the original, searched in the copy (whole tokens; >=4 chars):")
phones = {s for s in strings_o if an.PHONE_RE.match(s) and sum(c.isdigit() for c in s) >= 6}
ips = {s for s in strings_o if an.IP_RE.match(s) and (s.count(".") == 3 or s.count(":") >= 2)}
for field, vals in (("usernames", an.USERNAMES), ("emails", set(emails)), ("phone numbers", phones), ("IP addresses", ips)):
    vals = {v.casefold() for v in vals if len(v) >= 4}
    print(f"  {field}: {len(vals)} distinct, {sum(1 for v in vals if v in tokens)} found")
names = {n.casefold() for n in an.NAMES if len(n) >= 4 and " " in n}
print(f"  full names (with a space): {len(names)} distinct, {sum(1 for n in names if n in corpus)} found")
