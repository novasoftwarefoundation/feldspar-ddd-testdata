"""Anonymize an Instagram JSON export (zip in, zip out), keeping its structure.

    python3 anonymize.py <original.zip> <output.zip> [placeholders-dir]

placeholders-dir defaults to the placeholders/ folder next to this script.

Same entries in the same order, same JSON keys/nesting/list lengths/value types,
written in Meta's own byte format. Every personal value is replaced by a fake one;
a value is mapped through HMAC with a random key that is never stored, so the same
original always gets the same fake within one run, and the mapping can't be reversed.

Prints only counts (per action and per field kind), never a value.
"""
import collections
import hashlib
import hmac
import json
import os
import random
import re
import sys
import unicodedata
import zipfile
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(__file__))
import metajson  # noqa: E402

KEY = os.urandom(32)
STATS = collections.Counter()      # (action, field) -> count
UNSURE = collections.Counter()     # fields replaced because their kind was unclear


def rng_for(kind, value):
    digest = hmac.new(KEY, f"{kind}\0{value}".encode("utf-8", "surrogatepass"), hashlib.sha256).digest()
    return random.Random(digest)


# --- Meta's double-encoded UTF-8 ---------------------------------------------------------------

def unmoji(s):
    try:
        return s.encode("latin1").decode("utf-8"), True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s, False


def remoji(s, was):
    return s.encode("utf-8").decode("latin1") if was else s


# --- character-class scrambling ----------------------------------------------------------------

LOWER, UPPER, DIGITS = "abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"
ACC_LOWER, ACC_UPPER = "àáâäãåçèéêëìíîïñòóôöøùúûüýÿ", "ÀÁÂÄÃÅÇÈÉÊËÌÍÎÏÑÒÓÔÖØÙÚÛÜÝ"
EMOJI = "😀😃😄😁😆😅😂🙂😉😊😇😍🥰😘😋😎🤩🥳😏😌😴🤔🤗🙌👍👏🙏💪👀🔥✨🌟🎉🎈🌈☀️🌸🌻🍀🍕🍰☕🎵🎶❤️💙💚💛🧡💜🚲🏖️📷".replace("️", "")


def is_emoji(ch):
    return unicodedata.category(ch) == "So" or 0x1F000 <= ord(ch) <= 0x1FAFF


def scramble_char(ch, r):
    if ch in LOWER:
        return r.choice(LOWER)
    if ch in UPPER:
        return r.choice(UPPER)
    if ch in DIGITS:
        return r.choice(DIGITS)
    if ord(ch) < 128:
        return ch
    if 0x1F3FB <= ord(ch) <= 0x1F3FF:      # skin tone modifier: keep with the new base
        return ch
    if is_emoji(ch):
        return r.choice(EMOJI)
    cat = unicodedata.category(ch)
    if cat == "Ll" and ch in ACC_LOWER + "ßœ":
        return r.choice(ACC_LOWER)
    if cat == "Lu" and ch in ACC_UPPER:
        return r.choice(ACC_UPPER)
    if cat.startswith("L"):
        # another letter from the same script block, so the character type stays the same
        base = ord(ch) & ~0x7F
        for _ in range(50):
            c = chr(base + r.randrange(128))
            if unicodedata.category(c) == cat:
                return c
        return ch
    if cat == "Nd":
        return chr(ord(ch) - int(unicodedata.digit(ch)) + r.randrange(10))
    return ch                               # punctuation, spaces, ZWJ, variation selectors


def scramble(s, kind="scr", keep_letters=False):
    r = rng_for(kind, s)
    out = []
    for ch in s:
        if keep_letters and ch not in DIGITS:
            out.append(ch)
        else:
            out.append(scramble_char(ch, r))
    return "".join(out)


def scramble_ident(s, kind):
    """Scramble letters/digits, keep %XX escapes and separators."""
    r = rng_for(kind, s)
    return re.sub(r"%[0-9A-Fa-f]{2}|.", lambda m: m.group(0) if len(m.group(0)) == 3 else scramble_char(m.group(0), r), s,
                  flags=re.S)


# --- fake words, names, places -----------------------------------------------------------------

WORDS = """a al an at de el en et in is it la le of on to up we ad am as be by do go he if me my no or so us
ars bis cum dic est hoc ius lux mox non per pro qui res sed sic sol tam via vel aer bos dux fax nox pax rex
amet arma ante aqua ager alba ara bene cano casa cibo dies dona ecce fama fere hora iam ibi illa ipsa ita
labor mare mens mora nisi nunc odio opus pace quam quod rosa sine sunt tamen tibi unde urbs usus vita
ullam vitae velit lorem ipsum dolor magna terra porta lacus fugit nulla culpa dicta etiam ferre gaudi
habet iusta minor nobis orbis parva quasi regio saepe tempo verba aurum caelum ventus nostra semper
tempus mollis turpis cursus luctus varius sapien rhoncus ornare libero dapibus aliquam blandit commodo
egestas finibus gravida iaculis laoreet posuere pretium tellus ultrices viverra eleifend accumsan
consequat fermentum hendrerit imperdiet malesuada pellentesque scelerisque sollicitudin vestibulum
condimentum consectetur adipiscing exercitation reprehenderit voluptatem perspiciatis accusantium
doloremque laudantium architecto explicabo voluptatibus repudiandae necessitatibus""".split()
BY_LEN = collections.defaultdict(list)
for _w in WORDS:
    BY_LEN[len(_w)].append(_w)

FIRST = """Anna Bram Cas Daan Eva Femke Gijs Hanna Isa Jesse Kim Lars Lotte Mila Noah Olaf Pien Ruben Sanne Tim
Vera Wout Yara Zoe Ava Ben Chloe Dirk Emma Floor Gerrit Hugo Ilse Joris Koen Lieke Maud Niels Rosa Sem""".split()
LAST = """Jansen Bakker Visser Smit Meijer Mulder Bos Vos Peters Hendriks Dekker Brouwer Kok Jacobs Willems
Vermeulen Kuipers Veenstra Boer Prins Blom Huisman Kramer Schouten Post Vink Wolters Hoekstra Koster""".split()
CITIES = """Zwolle Assen Leeuwarden Deventer Apeldoorn Arnhem Breda Tilburg Venlo Delft Haarlem Alkmaar
Middelburg Lelystad Emmen Hengelo Gouda Dordrecht Almere Amersfoort""".split()
REGIONS = """Overijssel Drenthe Friesland Gelderland Brabant Limburg Zeeland Flevoland""".split()
COUNTRIES = ["Belgium", "Germany", "Denmark", "Austria", "Portugal", "Norway"]
CODES = ["BE", "DE", "DK", "AT", "PT", "NO"]
# plausible coordinates (Dutch towns), used for fake latitude/longitude
COORDS = [(52.5168, 6.0830), (52.9925, 6.5649), (53.2012, 5.7999), (52.2661, 6.1552), (51.9851, 5.8987),
          (51.5719, 4.7683), (51.5555, 5.0913), (51.3704, 6.1724), (52.0116, 4.3571), (52.3874, 4.6462)]


def fit_case(new, old):
    if old.isupper() and len(old) > 1:
        return new.upper()
    if old[:1].isupper():
        return new[:1].upper() + new[1:]
    return new


def fake_word(w, r):
    if w.isascii() and w.isalpha():
        pool = BY_LEN.get(len(w))
        if pool:
            return fit_case(r.choice(pool), w)
    return "".join(scramble_char(c, r) for c in w)


URL_IN_TEXT = re.compile(r"https?://\S+|www\.\S+")


def fake_text(s, kind="text"):
    """Fake text: same length per word, same character types; punctuation and spacing kept."""
    r = rng_for(kind, s)
    out, pos = [], 0
    for m in URL_IN_TEXT.finditer(s):
        out.append(_fake_plain(s[pos:m.start()], r))
        out.append(fake_url(m.group(0)) if m.group(0).startswith("http") else "www." + scramble_ident(m.group(0)[4:], "u"))
        pos = m.end()
    out.append(_fake_plain(s[pos:], r))
    return "".join(out)


def _fake_plain(s, r):
    def word(m):
        w = m.group(0)
        if w.startswith("@"):
            return "@" + fake_username(w[1:])
        return fake_word(w, r)
    s = re.sub(r"@[\w.]+|[^\W\d_]+", word, s)
    return "".join(scramble_char(c, r) if (c in DIGITS or is_emoji(c) or unicodedata.category(c) == "Nd") else c for c in s)


def fake_letters_only(s):
    """Replace words, keep digits and punctuation (aggregate stats like 'City: 12.5%')."""
    r = rng_for("letters", s)
    return re.sub(r"[^\W\d_]+", lambda m: fit_case(r.choice(CITIES), m.group(0)) if m.group(0)[:1].isupper() else fake_word(m.group(0), r), s)


def fake_username(u):
    return scramble(u, "user")


def fake_name(n):
    r = rng_for("name", n)
    parts = re.split(r"(\s+)", n)
    out, first = [], True
    for p in parts:
        if not p or p.isspace():
            out.append(p)
        elif p.isascii() and p.isalpha():
            out.append(fit_case((r.choice(FIRST) if first else r.choice(LAST)), p) if p[:1].isupper() else
                       fit_case((r.choice(FIRST) if first else r.choice(LAST)).lower(), p))
            first = False
        else:
            out.append("".join(scramble_char(c, r) for c in p))
            first = False
    return "".join(out)


def fake_email(e):
    r = rng_for("email", e)
    local, _, _ = e.partition("@")
    return scramble(local, "email-local") + "@" + r.choice(["example.com", "example.org", "example.net"])


def fake_phone(p):
    head = re.match(r"^\+?\d{0,2}", p).group(0)
    return head + scramble(p[len(head):], "phone")


def fake_ip(ip):
    r = rng_for("ip", ip)
    if ":" in ip:
        groups = ip.split(":")
        new = ["2001", "db8"] + ["%x" % r.randrange(65536) if g else "" for g in groups[2:]]
        return ":".join(new[:len(groups)])
    return "10.%d.%d.%d" % (r.randrange(256), r.randrange(256), 1 + r.randrange(254))


def fake_coord(v, axis):
    """axis 0 = latitude, 1 = longitude; keeps the number of decimals of a string value."""
    r = rng_for("coord%d" % axis, str(v))
    base = r.choice(COORDS)[axis] + r.uniform(-0.02, 0.02)
    if isinstance(v, str):
        dec = len(v.split(".")[1]) if "." in v else 0
        return f"{base:.{dec}f}"
    return round(base, 6)


def fake_place(s, kind="place"):
    r = rng_for(kind, s)
    parts = s.split(", ")
    out = []
    for i, p in enumerate(parts):
        if re.fullmatch(r"[A-Z]{2}", p):
            out.append(r.choice(CODES))
        elif i == 0:
            out.append(r.choice(CITIES))
        elif i == len(parts) - 1 and len(parts) > 1:
            out.append(r.choice(COUNTRIES))
        else:
            out.append(r.choice(REGIONS))
    return ", ".join(out)


def fake_dob(s):
    r = rng_for("dob", s)
    y, m, d = 1985 + r.randrange(15), 1 + r.randrange(12), 1 + r.randrange(28)
    return re.sub(r"\d{4}-\d{2}-\d{2}", f"{y:04d}-{m:02d}-{d:02d}", s) if re.search(r"\d{4}-\d{2}-\d{2}", s) else scramble(s, "dob")


# --- URLs and export paths ---------------------------------------------------------------------

META_HOSTS = re.compile(r"(^|\.)(instagram\.com|facebook\.com|threads\.net|threads\.com|fb\.com|fb\.me|instagr\.am|"
                        r"ig\.me|cdninstagram\.com|fbcdn\.net|fbsbx\.com|whatsapp\.com|wa\.me|meta\.com|messenger\.com)$")
STRUCT = {"", "p", "reel", "reels", "stories", "tv", "explore", "tags", "locations", "ads", "library", "_u", "direct",
          "t", "s", "highlights", "accounts", "post", "web", "share", "audio", "search", "about", "profile.php",
          "watch", "groups", "pages", "events", "photo", "photos", "videos", "story.php", "permalink.php", "people",
          "hashtag", "l.php", "music", "keyword", "popular", "channel", "embed"}
USERNAMES: set = set()
NAMES: set = set()


def fake_url(u):
    try:
        parts = urlsplit(u)
    except ValueError:
        return scramble_ident(u, "url")
    host = parts.hostname or ""
    if META_HOSTS.search(host):
        segs = parts.path.split("/")
        new = []
        for s in segs:
            if s in STRUCT:
                new.append(s)
            elif s in USERNAMES or s.lstrip("@") in USERNAMES:
                new.append(("@" if s.startswith("@") else "") + fake_username(s.lstrip("@")))
            else:
                new.append(scramble_ident(s, "seg"))
        netloc = parts.netloc
        path = "/".join(new)
    else:
        labels = host.split(".")
        keep_last = 1 if len(labels) > 1 else 0
        new_labels = [lab if (lab == "www" or i >= len(labels) - keep_last) else scramble_ident(lab, "host")
                      for i, lab in enumerate(labels)]
        netloc = parts.netloc.replace(host, ".".join(new_labels)) if host else parts.netloc
        path = "/".join(scramble_ident(s, "seg") for s in parts.path.split("/"))
    query = "&".join(
        (kv.split("=", 1)[0] + "=" + scramble_ident(kv.split("=", 1)[1], "q")) if "=" in kv else scramble_ident(kv, "q")
        for kv in parts.query.split("&")) if parts.query else ""
    frag = scramble_ident(parts.fragment, "frag") if parts.fragment else ""
    return urlunsplit((parts.scheme, netloc, path, query, frag)) + ("?" if u.endswith("?") and not query else "")


THREAD_DIR = re.compile(r"^(.*)_(\d+)$")


def fake_thread_dir(d):
    m = THREAD_DIR.match(d)
    if not m:
        return scramble(d, "thread")
    return scramble(m.group(1), "thread") + "_" + scramble(m.group(2), "thread-id")


MEDIA_ID = re.compile(r"^(\d)(\d{9,})(\.\w+)?$")


def fake_path(p):
    segs = p.split("/")
    for i in range(1, len(segs)):
        if segs[i - 1] in ("inbox", "message_requests", "filtered_threads", "archived_threads") and i < len(segs):
            segs[i] = fake_thread_dir(segs[i])
    # media file names are Instagram media ids, which lead back to the post: same length, new digits
    m = MEDIA_ID.match(segs[-1])
    if m:
        segs[-1] = m.group(1) + scramble(m.group(2), "media-id") + (m.group(3) or "")
    return "/".join(segs)


# --- value classification ----------------------------------------------------------------------

MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"


def looks_time(s):
    if not re.search(r"\d", s) or ":" not in s:
        return False
    rest = re.sub(MONTHS, "", s.lower())
    rest = re.sub(r"\b(am|pm|t|z|utc)\b|(?<=\d)(am|pm|t|z)", "", rest)
    return re.fullmatch(r"[\d\s:+\-.,/t]*", rest) is not None


IP_RE = re.compile(r"^(\d{1,3}(\.\d{1,3}){3}|[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){2,7})$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{6,}$")
BOOLS = {"True", "False", "true", "false"}

HEADINGS = {"Author", "Brand partner", "Hashtags", "Media", "Metadata", "Owner", "Place", "Profile change",
            "Reel metadata", "Repost", "Topics"}
NONPERSON_GROUPS = {"Hashtags", "Topics", "Place", "Media", "Metadata", "Reel metadata"}

KEEP_LABELS = {
    "Click type", "Email type", "Type", "Privacy", "Publish mode", "How you opened the camera",
    "How you opened the camera from the browser", "Media quality", "Output format", "Surface", "Source", "Feedback",
    "Channel", "Notification type", "Value", "Supported image compression format", "Supported SDK Versions",
    "Supported test versions of Meta's camera effects SDK", "Supported versions of Meta's camera effects SDK",
    "Language", "Language Code", "App", "App version", "Background color", "Text color", "Color",
    "Sharing audience", "Usage explanation", "Product Name", "Decision", "Reason", "Changed", "Private Account",
    "Is Eligible for Profile Activation Badge", "Profile Shows Activation Badge", "Emoji", "Amount raised",
    "File size in bytes", "Original height", "Original width", "Option 1 font size", "Option 2 font size",
    "Option 3 font size", "Option 4 font size", "Count", "How many times did you try to download the file?",
    "Emoji Pong High Score", "Duration",
}
KEEP_KEYS = {"source_app", "camera_position", "source_type", "scene_capture_type", "lens_make", "lens_model",
             "software", "focal_length", "aperture", "shutter_speed", "metering_mode", "date_time_digitized",
             "date_time_original", "reply_control", "geo_gated_country_list", "music_genre", "reaction"}
ACTION_BY_LABEL = {
    "Username": "username", "Media Owner": "username", "Author": "username",
    "Name": "name", "Profile Name": "name", "First Name": "name", "Last Name": "name", "First name": "name",
    "Last name": "name", "First/given name": "name", "Last/family name": "name",
    "Email": "email", "Email address": "email", "Latest email submitted during the email confirmation process": "email",
    "Phone number": "phone",
    "IP Address": "ip", "IP address": "ip",
    "Device ID": "id", "Cookie": "id", "Cookie Name": "id", "Draft identifier": "id", "Upload identifier": "id",
    "User Agent": "ua", "Port": "id", "Port number": "id",
    "Latitude": "lat", "Imprecise Latitude": "lat", "Precise Latitude": "lat",
    "Longitude": "lon", "Imprecise Longitude": "lon", "Precise Longitude": "lon",
    "Date of birth": "dob", "Birthday": "dob", "Gender": "gender",
    "City": "city", "Region": "region", "Country": "country", "State": "region", "First Country Code": "code",
    "Location": "place", "Locations of interest": "city", "ZIP/postal code": "id", "ZIP code": "id",
    "Website": "url", "Website link you visited": "url", "URL": "url", "Ad library public URL": "url",
    "Brand partner's profile": "url",
    "Follower Percentage by City": "letters", "Follower Percentage by Country": "letters",
    "Bio": "text", "Caption": "text", "Comment": "text", "Title": "text", "Question": "text", "Answer": "auto",
    "Option 1": "text", "Option 2": "text", "Option 3": "text", "Option 4": "text", "Message": "text",
    "Description": "text", "Title of website page you visited": "text", "Brand": "text", "Merchant name": "text",
    "Product name": "text", "Product names": "text", "Brand partner": "name", "Price": "text",
    "Contact Information": "auto", "New value": "auto", "Previous value": "auto",
}
KEY_ACTIONS = {"sender_name": "name", "actor": "name", "name": "name", "original_content_owner": "username",
               "content": "text", "share_text": "text", "link": "url", "href": "url", "uri": "path",
               "thread_path": "path", "device_id": "id"}
INSIGHTS = "past_instagram_insights/"
TEXT_FILES = ("advertisers_using_your_activity_or_information.json", "other_categories_used_to_reach_you.json",
              "recently_viewed_items.json")


def auto(v, field):
    if v == "" or v in BOOLS or looks_time(v):
        return v, "keep"
    if re.match(r"https?://", v):
        return fake_url(v), "url"
    if EMAIL_RE.match(v):
        return fake_email(v), "email"
    if IP_RE.match(v) and (v.count(".") == 3 or v.count(":") >= 2):
        return fake_ip(v), "ip"
    if v in USERNAMES:
        return fake_username(v), "username"
    if v in NAMES:
        return fake_name(v), "name"
    if PHONE_RE.match(v) and sum(c.isdigit() for c in v) >= 6:
        return fake_phone(v), "phone"
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return scramble(v, "num"), "id"
    return fake_text(v), "text"


def apply(action, v, field):
    """Returns the new value for string v."""
    if action == "auto":
        new, kind = auto(v, field)
        STATS[(kind, field)] += 1
        if kind != "keep":
            UNSURE[(field, kind)] += 1
        return new
    if v == "":
        return v
    STATS[(action, field)] += 1
    if action == "keep":
        return v
    if action == "username":
        return fake_username(v) if not looks_time(v) else v
    if action == "name":
        if EMAIL_RE.match(v):
            return fake_email(v)
        if re.fullmatch(r"[\d\s+\-()]+", v):
            return fake_phone(v)
        return fake_name(v)
    if action == "email":
        return fake_email(v) if EMAIL_RE.match(v) else scramble(v, "email")
    if action == "phone":
        return fake_phone(v)
    if action == "ip":
        return fake_ip(v)
    if action == "id":
        return scramble_ident(v, "id")
    if action == "ua":
        return scramble(v, "ua", keep_letters=True)
    if action == "lat":
        return fake_coord(v, 0)
    if action == "lon":
        return fake_coord(v, 1)
    if action == "dob":
        return fake_dob(v)
    if action == "gender":
        return "Prefer not to say"
    if action == "city":
        return rng_for("city", v).choice(CITIES)
    if action == "region":
        return rng_for("region", v).choice(REGIONS)
    if action == "country":
        return rng_for("country", v).choice(COUNTRIES)
    if action == "code":
        return rng_for("code", v).choice(CODES)
    if action == "place":
        return fake_place(v)
    if action == "url":
        return fake_url(v) if re.match(r"https?://", v) else fake_text(v)
    if action == "path":
        return fake_url(v) if re.match(r"https?://", v) else fake_path(v)
    if action == "letters":
        return fake_letters_only(v)
    if action == "text":
        return fake_text(v)
    raise ValueError(action)


# --- walking -----------------------------------------------------------------------------------

def label_action(label, group, fname):
    if fname.startswith(INSIGHTS) or "/" + INSIGHTS in fname:
        a = ACTION_BY_LABEL.get(label)
        return a if a in ("letters",) else "keep"
    if label in KEEP_LABELS:
        return "keep"
    if label == "Name" and group in NONPERSON_GROUPS:
        return "text"
    if fname.endswith(TEXT_FILES):
        return "text"
    if label == "Name" and group is None and fname.endswith(("saved_collections.json",)):
        return "text"
    return ACTION_BY_LABEL.get(label, "auto")


def str_value(v, action, field):
    raw, was = unmoji(v)
    return remoji(apply(action, raw, field), was)


def walk(node, fname, key=None, label=None, group=None, parent=None):
    if isinstance(node, dict):
        lab = node.get("label") if isinstance(node.get("label"), str) else None
        lab = unmoji(lab)[0] if lab else None
        title = node.get("title") if isinstance(node.get("title"), str) else None
        grp = group
        if title and unmoji(title)[0] in HEADINGS:
            grp = unmoji(title)[0]
        out = {}
        for k, v in node.items():
            if k == "label" and isinstance(v, str):
                out[k] = v
            elif k == "title" and isinstance(v, str):
                out[k] = title_value(v, node, fname, parent)
            elif k == "string_map_data" and isinstance(v, dict):
                out[k] = {mk: walk(mv, fname, "smd", unmoji(mk)[0], grp, node) for mk, mv in v.items()}
            elif k in ("value", "href") and lab is not None:
                out[k] = walk(v, fname, k, lab, grp, node)
            elif k == "vec" and lab is not None:
                out[k] = [walk(x, fname, "vec", lab, grp, node) for x in v]
            else:
                out[k] = walk(v, fname, k, label if key in ("smd", "vec") else None, grp, node)
        # Pair consistency for profile changes: the value kind follows the "Changed" field.
        return out
    if isinstance(node, list):
        return [walk(x, fname, key, label, group, parent) for x in node]
    if isinstance(node, float) and key in ("latitude", "longitude"):
        STATS[(key, key)] += 1
        return fake_coord(node, 0 if key == "latitude" else 1)
    if not isinstance(node, str):
        return node
    if label is not None:
        if key == "href":
            return str_value(node, "url", label)
        return str_value(node, label_action(label, group, fname), label)
    if key in KEEP_KEYS:
        STATS[("keep", key)] += 1
        return node
    if key in KEY_ACTIONS:
        return str_value(node, KEY_ACTIONS[key], key)
    return str_value(node, "auto", "key:" + str(key))


def title_value(v, node, fname, parent):
    t = unmoji(v)[0]
    if t == "" or t in HEADINGS:
        STATS[("keep", "title")] += 1
        return v
    if any(k in node for k in ("uri", "creation_timestamp", "media")) and "string_list_data" not in node:
        return str_value(v, "text", "title(caption)")
    if fname.endswith(("message_1.json",)) or "/messages/" in fname:
        return str_value(v, "name", "title(thread)")
    if "dict" in node or "vec" in node or "label" in node:
        UNSURE[("title(section)", "text")] += 1
        return str_value(v, "text", "title(section)")
    return str_value(v, "auto", "title")


def fix_profile_changes(orig, new):
    """profile_changes: Previous/New value follow the kind named in 'Changed'."""
    kinds = {"Username": "username", "Profile Name": "name", "Name": "name", "Email": "email", "Phone": "phone"}
    for o, n in zip(orig.get("profile_profile_change", []), new.get("profile_profile_change", [])):
        smd_o, smd_n = o["string_map_data"], n["string_map_data"]
        kind = kinds.get(unmoji(smd_o.get("Changed", {}).get("value", ""))[0])
        for f in ("Previous value", "New value"):
            if f in smd_o:
                a = kind or "text"
                smd_n[f]["value"] = str_value(smd_o[f]["value"], a, "profile change: " + f)


# --- collecting known usernames and names ------------------------------------------------------

def collect(node, label=None, key=None):
    if isinstance(node, dict):
        lab = unmoji(node["label"])[0] if isinstance(node.get("label"), str) else None
        for k, v in node.items():
            if k == "string_map_data" and isinstance(v, dict):
                for mk, mv in v.items():
                    collect(mv, unmoji(mk)[0], "smd")
            elif k in ("value",) and lab:
                collect(v, lab, k)
            else:
                collect(v, label if key == "smd" else None, k)
        if "string_list_data" in node:
            t = node.get("title")
            if isinstance(t, str) and t and not looks_time(t):
                USERNAMES.add(unmoji(t)[0])
            for it in node["string_list_data"]:
                if isinstance(it, dict) and isinstance(it.get("value"), str) and re.fullmatch(r"[\w.]{1,30}", it["value"]):
                    USERNAMES.add(it["value"])
                h = it.get("href") if isinstance(it, dict) else None
                if isinstance(h, str):
                    m = re.match(r"https?://(www\.)?(instagram\.com|threads\.net|threads\.com)/(_u/)?@?([\w.]+)/?$", h)
                    if m:
                        USERNAMES.add(m.group(4))
    elif isinstance(node, list):
        for x in node:
            collect(x, label, key)
    elif isinstance(node, str) and node:
        v = unmoji(node)[0]
        if label in ("Username", "Media Owner", "Author") or key == "original_content_owner":
            USERNAMES.add(v)
        elif label in ("Name", "Profile Name") or key in ("sender_name", "actor", "name"):
            NAMES.add(v)


# --- media placeholders ------------------------------------------------------------------------

def placeholder(name, data, ph):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name.rsplit("/", 1)[-1] else ""
    if data[:3] == b"\xff\xd8\xff" or ext in ("jpg", "jpeg"):
        return ph["jpg"]
    if data[:8] == b"\x89PNG\r\n\x1a\n" or ext == "png":
        return ph["png"]
    if ext in ("mp4", "m4a", "mov") or data[4:8] == b"ftyp":
        video, audio = b"vide" in data, b"soun" in data
        return ph["video_audio"] if video and audio else ph["video_only"] if video else ph["audio_only"]
    raise ValueError("unknown media type in " + ext)


def main(src, dst, phdir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "placeholders")):
    ph = {k: open(os.path.join(phdir, f), "rb").read() for k, f in
          (("jpg", "p.jpg"), ("png", "p.png"), ("video_audio", "video_audio.mp4"), ("video_only", "video_only.mp4"),
           ("audio_only", "audio_only.mp4"))}
    zin = zipfile.ZipFile(src)
    parsed = {}
    for info in zin.infolist():
        if info.filename.endswith(".json"):
            parsed[info.filename] = json.loads(zin.read(info))
            collect(parsed[info.filename])
    NAMES.discard("")
    USERNAMES.discard("")
    print("known usernames:", len(USERNAMES), "known names:", len(NAMES))
    # fake words must never spell an original name or username by coincidence
    taken = {w.casefold() for x in NAMES | USERNAMES for w in re.findall(r"[^\W\d_]+", x)}
    for n in list(BY_LEN):
        BY_LEN[n] = [w for w in BY_LEN[n] if w.casefold() not in taken]
        if not BY_LEN[n]:
            del BY_LEN[n]
    FIRST[:] = [w for w in FIRST if w.casefold() not in taken]
    LAST[:] = [w for w in LAST if w.casefold() not in taken]
    CITIES[:] = [w for w in CITIES if w.casefold() not in taken]
    print("fake pools after removing words used in originals: words", sum(map(len, BY_LEN.values())),
          "first names", len(FIRST), "last names", len(LAST), "cities", len(CITIES))
    files = collections.Counter()
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            name = fake_path(info.filename)
            if info.filename.endswith(".json"):
                data = parsed[info.filename]
                new = walk(data, info.filename)
                if info.filename.endswith("profile_changes.json"):
                    fix_profile_changes(data, new)
                body = metajson.dumps(new).encode("ascii")
                files["json"] += 1
            else:
                body = placeholder(info.filename, zin.read(info), ph)
                files["media"] += 1
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, body)
    print("files:", dict(files), "renamed entries:", sum(fake_path(i.filename) != i.filename for i in zin.infolist()))
    agg = collections.Counter()
    for (action, field), n in STATS.items():
        agg[action] += n
    print("replacements by kind:", dict(sorted(agg.items())))
    print("fields without a fixed rule, replaced by detected type:")
    for (fld, kind), n in sorted(UNSURE.items()):
        print(f"   {fld} -> {kind}: {n}")
    with open(os.path.join(os.path.dirname(dst) or ".", "field-actions.json"), "w") as f:
        json.dump(sorted([a, fld, n] for (a, fld), n in STATS.items()), f, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
