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


SALT = [""]      # set while re-drawing a fake that collided with another original's fake


def rng_for(kind, value):
    digest = hmac.new(KEY, f"{kind}{SALT[0]}\0{value}".encode("utf-8", "surrogatepass"), hashlib.sha256).digest()
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


def pick(r, pool, original):
    """A fake from the pool, or the original's letters scrambled when every pool word occurs in the originals
    (an address book can hold every fake first name)."""
    return r.choice(pool) if pool else "".join(scramble_char(c, r) for c in original)


def fake_word(w, r):
    if w.isascii() and w.isalpha():
        pool = BY_LEN.get(len(w))
        if pool:
            return fit_case(r.choice(pool), w)
    return "".join(scramble_char(c, r) for c in w)


URL_IN_TEXT = re.compile(r"https?://\S+|www\.\S+")


def fake_text(s, kind="text"):
    """Fake text: same length per word, same character types; punctuation and spacing kept."""
    if not any(c.isalnum() for c in s):
        return s        # only emoji / punctuation (e.g. a single reaction emoji): identifies nobody
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
    return re.sub(r"[^\W\d_]+", lambda m: fit_case(pick(r, CITIES, m.group(0)), m.group(0)) if m.group(0)[:1].isupper() else fake_word(m.group(0), r), s)


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
            new = pick(r, FIRST if first else LAST, p)
            out.append(fit_case(new, p) if p[:1].isupper() else fit_case(new.lower(), p))
            first = False
        else:
            out.append("".join(scramble_char(c, r) for c in p))
            first = False
    return "".join(out)


def fake_email(e):
    r = rng_for("email", e)
    local, _, _ = e.partition("@")
    return scramble(local, "email-local") + "@" + r.choice(["voorbeeldpost.test", "nepmail.test", "testbus.test"])


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
    try:
        if float(v) == 0:
            return v        # 0 means "no location": nothing to hide, and a fake would invent one
    except ValueError:
        pass
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
            out.append(pick(r, CITIES, p))
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


def fake_netloc(netloc, host):
    """Scramble the host as written in netloc (urlsplit's hostname is lowercased, so a capitalised host would not
    be found in netloc); www and the top-level domain are kept, user info and port too."""
    at = netloc.lower().find(host) if host else -1
    if at < 0:
        return netloc
    labels = netloc[at:at + len(host)].split(".")
    keep_last = 1 if len(labels) > 1 else 0
    new = ".".join(lab if lab.lower() == "www" or i >= len(labels) - keep_last else scramble_ident(lab, "host")
                   for i, lab in enumerate(labels))
    return netloc[:at] + new + netloc[at + len(host):]


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
        netloc = fake_netloc(parts.netloc, host)
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


MEDIA_KEEP_TOKENS = {"n", "video", "dashinit", "audioclip", "thumbnail", "s", "o", "a"}


def fake_media_name(seg):
    """Media file names are CDN / media ids that lead back to the post: same shape, new characters."""
    stem, dot, ext = seg.rpartition(".") if re.search(r"\.[A-Za-z0-9]{2,5}$", seg) else (seg, "", "")
    out = []
    for tok in stem.split("_"):
        m = re.fullmatch(r"([a-z]+)(\d+)", tok)
        if tok in MEDIA_KEEP_TOKENS or tok == "":
            out.append(tok)
        elif m and m.group(1) in MEDIA_KEEP_TOKENS:
            out.append(m.group(1) + scramble(m.group(2), "media-tok"))
        elif tok.isdigit():
            out.append(tok[0] + scramble(tok[1:], "media-id"))
        elif re.fullmatch(r"[0-9A-F]+|[0-9a-f]+", tok):
            r = rng_for("media-hex", tok)
            hexd = "0123456789ABCDEF" if tok.upper() == tok else "0123456789abcdef"
            out.append("".join(r.choice(hexd) for _ in tok))
        else:
            out.append(scramble_ident(tok, "media-tok"))
    return "_".join(out) + dot + ext


def fake_path(p):
    segs = p.split("/")
    for i in range(1, len(segs)):
        if segs[i - 1] in ("inbox", "message_requests", "filtered_threads", "archived_threads") and i < len(segs):
            segs[i] = fake_thread_dir(segs[i])
    # media file names carry media / CDN ids: same shape, new characters (folders like 202410 stay)
    last = segs[-1]
    if (re.search(r"\d", last) and not last.endswith((".json", ".txt")) and not re.fullmatch(r"\d{6}", last)
            and not (len(segs) > 1 and segs[-2] in ("inbox", "message_requests", "filtered_threads", "archived_threads"))):
        segs[-1] = fake_media_name(last)
    return "/".join(segs)


# --- value classification ----------------------------------------------------------------------

MONTHS = r"(jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)[a-zä]*|uhr"


def looks_time(s):
    if not re.search(r"\d", s) or ":" not in s:
        return False
    rest = re.sub(MONTHS, "", s.lower())
    rest = re.sub(r"\b(am|pm|t|z|utc)\b|(?<=\d)(am|pm|t|z)", "", rest)
    return re.fullmatch(r"[\d\s:+\-.,/t]*", rest) is not None


IP_RE = re.compile(r"^(\d{1,3}(\.\d{1,3}){3}|[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){2,7})$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{6,}$")
BOOLS = {"True", "False", "true", "false", "Waar", "Niet waar"}     # Dutch exports write booleans in words

HEADINGS = {"Author", "Brand partner", "Hashtags", "Media", "Metadata", "Owner", "Place", "Profile change",
            "Reel metadata", "Repost", "Topics",
            # Dutch exports
            "Auteur", "Merkpartner", "Eigenaar", "Plaats", "Reel-metagegevens", "Onderwerpen"}
NONPERSON_GROUPS = {"Hashtags", "Topics", "Place", "Media", "Metadata", "Reel metadata",
                    "Onderwerpen", "Plaats", "Reel-metagegevens"}
NAME_LABELS = {"Name", "Naam"}
EMPTY_SECTIONS = collections.Counter()    # titles of sections with an empty dict: repeated ones are Meta headings

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
    # German exports
    "Aktualisierung auf App-übergreifendes Messaging durchgeführt", "Consent Status",
    "Einstellung für Promos für exklusive Stories", "Entscheidung", "Grund", "Name des Produkts", "Komprimierung",
    "Unterstützte SDK-Versionen", "Gesichtserkennungs-Version", "Kommentieren gestattet für",
    "Methode zur Bestätigung der Telefonnummer", "Sprachcode", "Privates Konto", "Kontaktsynchronisierung",
    "Telefonnummer bestätigt", "Hat ein Live-Video geteilt",
    # Dutch exports
    "Besluit", "Reden", "Productnaam", "Contacten synchroniseren", "Doelgroep delen", "Evenement", "E-mailtype",
    "Heb je gearchiveerde reels?", "Hoe je de camera hebt geopend", "Hoe je de camera hebt geopend vanuit de browser",
    "Mediakwaliteit", "Uitvoerindeling", "Originele mediatype", "Publicatiemodus", "Taal", "Landcode",
    "Eerste landcode", "Uitleg van gebruik", "Ondersteunde SDK-versies", "Ondersteunde indeling voor afbeeldingscompressie",
    "Ondersteunde testversies van de SDK voor camera-effecten van Meta",
    "Ondersteunde versies van de SDK voor camera-effecten van Meta", "Appversie", "Aantal", "Ingezamelde bedrag",
    "Bestandsgrootte in bytes", "Oorspronkelijke hoogte", "Originele breedte", "Duur", "Camerapositie",
    "Phone Confirmation Method", "Heeft een livevideo gedeeld", "Hoe vaak heb je geprobeerd het bestand te downloaden?",
    "Jou scheiden van je achtergrond", "duration", "Primair e-mailadres",
}
KEEP_KEYS = {"device_manufacturer", "device_model", "device_os_version", "device_type", "type",
             "source_app", "camera_position", "source_type", "scene_capture_type", "lens_make", "lens_model",
             "software", "focal_length", "aperture", "shutter_speed", "metering_mode", "date_time_digitized",
             "date_time_original", "reply_control", "geo_gated_country_list", "music_genre", "reaction", "duration"}
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
    "City": "city", "Region": "region", "Country": "country", "State": "region", "First Country Code": "keep",
    "Location": "place", "Locations of interest": "city", "ZIP/postal code": "id", "ZIP code": "id",
    "Website": "url", "Website link you visited": "url", "URL": "url", "Ad library public URL": "url",
    "Brand partner's profile": "url",
    "Follower Percentage by City": "letters", "Follower Percentage by Country": "letters",
    "Bio": "text", "Caption": "text", "Comment": "text", "Title": "text", "Question": "text", "Answer": "auto",
    "Option 1": "text", "Option 2": "text", "Option 3": "text", "Option 4": "text", "Message": "text",
    "Description": "text", "Title of website page you visited": "text", "Brand": "text", "Merchant name": "text",
    "Product name": "text", "Product names": "text", "Brand partner": "name", "Price": "text",
    "Contact Information": "auto", "New value": "auto", "Previous value": "auto",
    # German exports
    "Benutzername": "username", "Nutzername": "username", "E-Mail-Adresse": "email", "E-Mail": "email",
    "Telefonnummer": "phone", "Geschlecht": "gender", "Name der Stadt": "city", "Geräte-ID": "id", "Gerät": "text",
    "IP-Adresse": "ip", "Name des Cookies": "id", "Ungenauer Breitengrad": "lat", "Ungenauer Längengrad": "lon",
    "Genauer Breitengrad": "lat", "Genauer Längengrad": "lon", "Suche": "auto", "Vorname": "name", "Nachname": "name",
    "Kontaktinformationen": "auto", "Erstes Länderkennzeichen": "keep", "Geburtsdatum": "dob", "Biografie": "text",
    "Kommentar": "text", "Eigentümer": "username", "Medieninhaber": "username", "Saved on": "url",
    # Dutch exports
    "Gebruikersnaam": "username", "Media-eigenaar": "username", "Naam": "name", "Voornaam": "name",
    "Achternaam": "name", "Profielnaam": "name", "Merkpartner": "name",
    "E-mailadres": "email",
    "Laatste e-mailadres dat is ingediend tijdens het bevestigingsproces voor e-mailadressen": "email",
    "Telefoonnummer": "phone", "IP-adres": "ip", "Apparaat-ID": "id", "Gebruikersagent": "ua", "Poortnummer": "id",
    "Breedtegraad": "lat", "Onnauwkeurige breedtegraad": "lat", "Exacte breedtegraad": "lat",
    "Lengtegraad": "lon", "Onnauwkeurige lengtegraad": "lon", "Exacte lengtegraad": "lon",
    "Geboortedatum": "dob", "Geslacht": "gender", "Stad": "city", "Plaats": "city", "Regio": "region",
    "Staat/provincie": "region", "Land": "country", "Landnaam": "country", "Locatie": "place",
    "Interessante locaties": "city", "Postcode": "id", "Postcode-extensie": "id",
    "Websitelink die je hebt bezocht": "url", "Openbare URL advertentiebibliotheek": "url",
    "Profiel van merkpartner": "url",
    "Volgerpercentage per stad": "letters", "Volgerpercentage per land": "letters",
    "Bio": "text", "Biografie": "text", "Onderschrift": "text", "Bijschrift": "text", "Titel": "text", "Opmerking": "text",
    "Reactie": "text", "Tekst": "text", "Bericht": "text", "Vraag": "text", "Beschrijving": "text",
    "Advertentietitel": "text", "Titel van websitepagina die je hebt bezocht": "text", "Productnamen": "text",
    "Merk": "text", "Prijs": "text", "Antwoord": "auto", "Contactgegevens": "auto",
    "Nieuwe waarde": "auto", "Vorige waarde": "auto",
}
KEY_ACTIONS = {"advertiser_name": "text", "last_connected_ip": "ip", "sender_name": "name", "actor": "name", "name": "name", "original_content_owner": "username",
               "content": "text", "share_text": "text", "link": "url", "href": "url", "uri": "path",
               "thread_path": "path", "device_id": "id"}
INSIGHTS = "past_instagram_insights/"
TEXT_FILES = ("advertisers_using_your_activity_or_information.json", "other_categories_used_to_reach_you.json",
              "your_topics.json",
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


META_WORDS = {"instagram", "facebook", "meta", "threads", "whatsapp", "messenger", "instagram lite", "facebook lite"}
MANY_TO_ONE = {"keep", "gender", "city", "region", "country", "code"}
FAKE_CACHE: dict = {}       # (action, original) -> fake
FAKE_OWNER: dict = {}       # casefolded fake -> original
ORIGINALS_CF: set = set()   # every original string (casefolded): a fake must never equal one
ORIG_TOKENS: set = set()    # every 4+ character token of the originals: a fake must not bring one in
_TOKEN_RES = (re.compile(r"[^\s\"',;:!?()\[\]{}<>]+"), re.compile(r"[\w.@+\-]+"), re.compile(r"[^/?&=#:.+%\s]+"))


def tokens_of(s):
    c = s.casefold()
    return {t for rx in _TOKEN_RES for t in rx.findall(c) if len(t) >= 4}


ORIG_SUBS: set = set()      # original tokens and short values of 6..30 characters, matched as substrings


def _brings_original_token(new, v):
    """True when the fake brings in an original token (4+ chars, whole) or an original piece (6..30 chars,
    anywhere in it) that its own original did not already contain."""
    if not ORIG_TOKENS:
        return False
    if (tokens_of(new) - tokens_of(v)) & ORIG_TOKENS:
        return True
    c, vc = new.casefold(), v.casefold()
    for n in range(6, min(30, len(c)) + 1):
        for i in range(len(c) - n + 1):
            w = c[i:i + n]
            if w in ORIG_SUBS and w not in vc:
                return True
    return False
COLLISIONS = collections.Counter()
IDENTITY_REDRAW = {"name", "username", "email", "phone", "ip", "id"}   # a fake that equals its own original is re-drawn


def apply(action, v, field):
    """Returns the new value for string v; distinct originals get distinct fakes."""
    key = (action, v)
    if key in FAKE_CACHE:
        if action == "auto":
            STATS[("auto-cached", field)] += 1
        return FAKE_CACHE[key]
    new = _apply(action, v, field)
    n = 0
    while (new and action not in MANY_TO_ONE and n < 60
           and ((new == v and action in IDENTITY_REDRAW and any(c.isalnum() for c in v))
                or new != v and ((new.casefold() in FAKE_OWNER and FAKE_OWNER[new.casefold()] != v)
                                 or new.casefold() in ORIGINALS_CF or _brings_original_token(new, v)))):
        n += 1
        SALT[0] = f"#{n}"
        new = _apply(action, v, field) if n < 30 else scramble(v, "collision")
        SALT[0] = ""
    if n:
        why = ("equals its own original" if new == v and any(c.isalnum() for c in v)
               else "other original's fake" if new.casefold() in FAKE_OWNER and FAKE_OWNER[new.casefold()] != v
               else "equals an original" if new.casefold() in ORIGINALS_CF
               else "brings an original token" if _brings_original_token(new, v) else None)
        COLLISIONS["re-drawn" if why is None else "unresolved: " + why + " (" + action + ")"] += 1
    if new and new != v:
        FAKE_OWNER.setdefault(new.casefold(), v)
    FAKE_CACHE[key] = new
    return new


def _apply(action, v, field):
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
        if v in USERNAMES:
            return fake_username(v)
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
        return pick(rng_for("city", v), CITIES, v)
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
    if action == "csv-id":
        if re.fullmatch(r"UC[\w-]{22}", v):
            return "UC" + scramble_ident(v[2:], "yt-id")
        return scramble_ident(v, "yt-id")
    if action == "header":
        labels = v.split(".")
        return ".".join(lab if lab == "www" or i == len(labels) - 1 else scramble_ident(lab, "host")
                        for i, lab in enumerate(labels))
    if action == "text" and v.casefold() in META_WORDS:
        return v        # Meta's own product name (e.g. an advertiser called "Instagram"): identifies nobody
    if action == "text":
        return fake_text(v)
    raise ValueError(action)


# --- walking -----------------------------------------------------------------------------------

def label_action(label, group, fname):
    if fname.startswith(INSIGHTS) or "/" + INSIGHTS in fname:
        a = ACTION_BY_LABEL.get(label)
        return a if a in ("letters", "text") else "keep"
    if label in KEEP_LABELS:
        return "keep"
    if label in NAME_LABELS and group in NONPERSON_GROUPS:
        return "text"
    if fname.endswith(TEXT_FILES):
        return "text"
    if label in NAME_LABELS and group is None and fname.endswith(("saved_collections.json",)):
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
    if key == "name" and "off_meta" in fname:
        return str_value(node, "text", "name(app or website)")
    if key in KEY_ACTIONS:
        return str_value(node, KEY_ACTIONS[key], key)
    return str_value(node, "auto", "key:" + str(key))


def title_value(v, node, fname, parent):
    t = unmoji(v)[0]
    if t == "" or t in HEADINGS or (node.get("dict") == [] and EMPTY_SECTIONS[t] >= 5):
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
        if node.get("dict") == [] and isinstance(node.get("title"), str) and node["title"]:
            EMPTY_SECTIONS[unmoji(node["title"])[0]] += 1
        for k, v in node.items():
            if k == "string_map_data" and isinstance(v, dict):
                for mk, mv in v.items():
                    collect(mv, unmoji(mk)[0], "smd")
            elif k in ("value",) and lab:
                collect(v, lab, k)
            else:
                collect(v, label if key == "smd" else None, k)
        if "string_map_data" in node and "string_list_data" not in node:
            t = node.get("title")
            if isinstance(t, str) and t and not looks_time(t):
                USERNAMES.add(unmoji(t)[0])
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
        if label in ("Username", "Media Owner", "Author", "Benutzername", "Nutzername", "Eigentümer",
                     "Medieninhaber", "Gebruikersnaam", "Media-eigenaar") or key == "original_content_owner":
            USERNAMES.add(v)
        elif (label in ("Name", "Profile Name", "Vorname", "Nachname", "Naam", "Voornaam", "Achternaam", "Profielnaam",
                        "First Name", "Last Name", "First name", "Last name")
              or key in ("sender_name", "actor", "name")):
            NAMES.add(v)


def _all_strings(n):
    if isinstance(n, dict):
        for v in n.values():
            _all_strings(v)
    elif isinstance(n, list):
        for x in n:
            _all_strings(x)
    elif isinstance(n, str) and n:
        ORIGINALS_CF.add(n.casefold())
        ORIGINALS_CF.add(unmoji(n)[0].casefold())
        for x in (n, unmoji(n)[0]):
            t = tokens_of(x)
            ORIG_TOKENS.update(t)
            ORIG_SUBS.update(w for w in t if 6 <= len(w) <= 30)
            if 6 <= len(x) <= 30:
                ORIG_SUBS.add(x.casefold())


# --- media placeholders ------------------------------------------------------------------------

SRT_META = re.compile(r"\d+|\d\d:\d\d:\d\d[,.]\d+ --> \d\d:\d\d:\d\d[,.]\d+.*")


def fake_srt(data):
    """Subtitles (reels captions): cue numbers, timings and line breaks kept; caption lines become fake text."""
    out = []
    for line in data.decode("utf-8").split("\n"):
        body = line.rstrip("\r")
        if body.strip() and not SRT_META.fullmatch(body.strip()):
            body = apply("text", body, "srt caption")
        out.append(body + line[len(line.rstrip("\r")):])
    return "\n".join(out).encode("utf-8")


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
            _all_strings(parsed[info.filename])
    NAMES.discard("")
    USERNAMES.discard("")
    print("known usernames:", len(USERNAMES), "known names:", len(NAMES))
    # fake words must never spell an original name or username by coincidence
    taken = {w.casefold() for x in NAMES | USERNAMES for w in re.findall(r"[^\W\d_]+", x)}
    # ... nor contain one of 6+ letters (the verifier's substring threshold), e.g. a surname inside a longer one
    long_taken = {w for w in taken if len(w) >= 6}
    taken |= {w.casefold() for pool in [FIRST, LAST, CITIES] + list(BY_LEN.values()) for w in pool
              if any(t in w.casefold() for t in long_taken)}
    for n in list(BY_LEN):
        BY_LEN[n] = [w for w in BY_LEN[n] if w.casefold() not in taken]
        if not BY_LEN[n]:
            del BY_LEN[n]
    FIRST[:] = [w for w in FIRST if w.casefold() not in taken]
    LAST[:] = [w for w in LAST if w.casefold() not in taken]
    CITIES[:] = [w for w in CITIES if w.casefold() not in taken]
    # same for regions and countries; an original may be a page named after one (keep the pool if it would empty)
    taken_all = taken | ORIGINALS_CF
    for pool in (REGIONS, COUNTRIES):
        pool[:] = [w for w in pool if w.casefold() not in taken_all] or pool
    print("fake pools after removing words used in originals: words", sum(map(len, BY_LEN.values())),
          "first names", len(FIRST), "last names", len(LAST), "cities", len(CITIES))
    files = collections.Counter()
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            name = fake_path(info.filename.rstrip("/")) + ("/" if info.is_dir() else "")
            if info.is_dir():
                body = b""
                files["dir"] += 1
            elif info.filename.endswith("no-data.txt"):
                body = zin.read(info)          # Meta's fixed "no data" notice
                files["no-data"] += 1
            elif info.filename.endswith(".srt"):
                body = fake_srt(zin.read(info))
                files["srt"] += 1
            elif info.filename.endswith(".json"):
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
    print("files:", dict(files), "renamed entries:",
          sum(fake_path(i.filename.rstrip("/")) != i.filename.rstrip("/") for i in zin.infolist()))
    agg = collections.Counter()
    for (action, field), n in STATS.items():
        agg[action] += n
    print("replacements by kind:", dict(sorted(agg.items())))
    print("fake collisions:", dict(COLLISIONS) or "none")
    print("fields without a fixed rule, replaced by detected type:")
    for (fld, kind), n in sorted(UNSURE.items()):
        print(f"   {fld} -> {kind}: {n}")
    with open(os.path.join(os.path.dirname(dst) or ".", "field-actions.json"), "w") as f:
        json.dump(sorted([a, fld, n] for (a, fld), n in STATS.items()), f, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
