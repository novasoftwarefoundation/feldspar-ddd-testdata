"""Read one package (zip) and describe its structure, never its values.

The result is a snapshot: for each file pattern its kind and, for JSON files, a
JSON Schema (draft 2020-12) with keys, nesting, types and the platform's own
field labels. Names that can hold personal data (usernames, ids, dates, user
text) are replaced by placeholders such as <name>_<id>. Anything the extractor
is unsure about is left out and counted in `left_out`, by pattern only.
"""
import collections
import csv
import io
import json
import re
import zipfile

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
TYPE_ORDER = ["object", "array", "string", "integer", "number", "boolean", "null"]
MEDIA = {"jpg", "jpeg", "png", "gif", "webp", "heic", "mp4", "mov", "m4a", "mp3", "aac", "wav", "webm",
         "dat", "srt", "vtt", "pdf"}
TEXT_KINDS = {"html": "html", "htm": "html", "csv": "csv", "txt": "text", "json": "json", "ics": "text",
              "vcf": "text", "xml": "text", "mbox": "text"}

UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
HEX = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-fA-F]*[a-fA-F])(?=[0-9a-fA-F]*[0-9])[0-9a-fA-F]{16,}|(?<=_)[0-9a-f]{16,}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
URL = re.compile(r"https?://\S+")
DIGITS = re.compile(r"\d{4,}")
# Long tokens of mixed letters and digits (base64 ids, media keys): T8VAigCQzMsF0AfN…
TOKEN = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Z])(?=[A-Za-z0-9_-]*[a-z])[A-Za-z0-9_-]{16,}")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")
LOCAL_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER = re.compile(r"<[a-z]+>")

# Keys whose string values are the platform's own field labels (Meta's label_values).
LABEL_KEYS = {"label"}


def meta_fix(text):
    """Undo Meta's double-encoded UTF-8 ("EigentÃ¼mer" -> "Eigentümer"); other text is unchanged."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _digits(match):
    run = match.group(0)
    if len(run) == 6 and run.startswith(("19", "20")):
        return "<yyyymm>"
    if len(run) == 8 and run.startswith(("19", "20")):
        return "<yyyymmdd>"
    return "<id>"


def id_pattern(text):
    """Replace ids, hashes, emails, URLs and long numbers by placeholders."""
    out = URL.sub("<url>", text)
    out = EMAIL.sub("<email>", out)
    out = UUID.sub("<uuid>", out)
    out = HEX.sub("<hex>", out)
    out = TOKEN.sub("<id>", out)
    out = DIGITS.sub(_digits, out)
    # A word with an id glued to letters (a handle such as "ab1234cd") is an id as a whole.
    out = re.sub(r"[A-Za-z0-9]*(?:[A-Za-z0-9]<id>|<id>[A-Za-z0-9])[A-Za-z0-9]*", "<id>", out)
    return out


class Values:
    """Every string value of a package, lowercased, to recognise names and keys that hold user data."""

    def __init__(self, wording=()):
        self.values = set()
        self.keys = set()
        # Words listed as the platform's own wording in files.yaml are never treated as user data.
        self.wording = {w.casefold() for w in wording}

    def add(self, text):
        text = text.strip().casefold()
        if len(text) >= 3:
            self.values.add(text)

    def add_key(self, key):
        self.keys.add(key.strip().casefold())

    def contains(self, text):
        """True when `text` is a whole value of the package and not also one of its JSON keys
        (a word the platform uses as a key, such as "media" or "title", is its own wording)."""
        text = text.strip().casefold()
        return text in self.values and text not in self.keys and text not in self.wording

    def replace_tokens(self, text, keep_capitalised=False):
        """Replace each word of `text` that is also a whole value of the package by <value>.

        With keep_capitalised, words such as "Owner" or "Reels" are kept: in keys, those are the
        platform's wording, while handles and usernames are written in lower case or with digits.
        """
        if self.contains(text):
            return "<value>", True
        hit = False

        def sub(match):
            nonlocal hit
            word = match.group(0)
            if keep_capitalised and re.fullmatch(r"[A-Z][a-z]*|[A-Z]+", word):
                return word
            if self.contains(word):
                hit = True
                return "<value>"
            return match.group(0)

        out = re.sub(r"[^\W_]{3,}(?:[._-][^\W_]+)*", sub, text)
        return out, hit


def normalise_segment(segment, is_file, values, left_out, where):
    stem, dot, ext = segment.rpartition(".") if is_file and "." in segment else (segment, "", "")
    out = id_pattern(stem)
    out, hit = values.replace_tokens(out)
    if hit:
        left_out[f"name part replaced by <value>: {where}"] += 1
    # A trailing small number numbers the parts of one file (message_1.json, followers_2.json).
    out = re.sub(r"_(\d{1,3})$", "_<n>", out)
    # Something followed by an id (thread folders such as "<username>_<id>") hides a name.
    if re.search(r"_<id>$" if is_file else r"_<(id|hex)>$", out):
        out = "<name>_<id>"
    # A file name made of ids only (media files such as <id>_<hex>_n_<hex>.jpg) is one id.
    if is_file and PLACEHOLDER.search(out) and len(re.sub(r"[^A-Za-z]", "", PLACEHOLDER.sub("", out))) < 3:
        out = "<id>"
    if len(out) > 80 or "\n" in out:
        out = "<text>"
        left_out[f"long name replaced by <text>: {where}"] += 1
    return out + (dot + ext if dot else "")


def path_pattern(name, values, left_out):
    parts = name.split("/")
    out = []
    for i, part in enumerate(parts):
        is_file = i == len(parts) - 1
        where = "/".join(out + ["…"]) if out else "(top)"
        out.append(normalise_segment(part, is_file, values, left_out, where))
    return "/".join(out)


def kind_of(name):
    ext = name.rpartition(".")[2].lower() if "." in name.rpartition("/")[2] else ""
    if ext in TEXT_KINDS:
        return TEXT_KINDS[ext], ext
    if ext in MEDIA or not ext:
        return "media", ext
    return "other", ext


class Node:
    """What one place in a JSON tree held across all instances in a package."""

    def __init__(self):
        self.types = set()
        self.objects = 0
        self.props = {}
        self.prop_counts = collections.Counter()
        self.patterns = set()
        self.items = None
        self.string_formats = collections.Counter()
        self.number_formats = collections.Counter()
        self.strings = 0
        self.numbers = 0
        self.labels = collections.Counter()


def number_format(value):
    if isinstance(value, bool):
        return None
    if 1e9 <= value < 4e9:
        return "unix-seconds"
    if 1e12 <= value < 4e12:
        return "unix-milliseconds"
    return None


def string_format(value):
    if ISO_DATETIME.match(value):
        return "date-time"
    if LOCAL_DATETIME.match(value):
        return "x-local-date-time"
    if DATE.match(value):
        return "date"
    if URL.fullmatch(value):
        return "uri"
    if EMAIL.fullmatch(value):
        return "email"
    return None


class Extractor:
    def __init__(self, platform, wording=()):
        self.platform = platform
        self.values = Values(wording)
        self.left_out = collections.Counter()

    # Pass 1: collect values so names and keys holding user data can be recognised.
    def collect(self, value, key=None):
        if isinstance(value, dict):
            for k, v in value.items():
                self.values.add_key(k)
                self.collect(v, k)
        elif isinstance(value, list):
            for v in value:
                self.collect(v, key)
        elif isinstance(value, str) and key not in LABEL_KEYS:
            self.values.add(value)

    def key_pattern(self, key, where):
        out = id_pattern(key)
        out, hit = self.values.replace_tokens(out, keep_capitalised=True)
        if hit:
            self.left_out[f"key part replaced by <value>: {where}"] += 1
        if len(out) > 80 or "\n" in out:
            self.left_out[f"long key replaced by <text>: {where}"] += 1
            out = "<text>"
        return out

    # Pass 2: describe the shape.
    def feed(self, node, value, where, key=None):
        if isinstance(value, dict):
            node.types.add("object")
            node.objects += 1
            seen = set()
            for k, v in value.items():
                name = self.key_pattern(k, where)
                if PLACEHOLDER.search(name):
                    node.patterns.add(name)
                child = node.props.setdefault(name, Node())
                if name not in seen:
                    node.prop_counts[name] += 1
                    seen.add(name)
                self.feed(child, v, f"{where}.{name}", k)
        elif isinstance(value, list):
            node.types.add("array")
            if node.items is None:
                node.items = Node()
            for v in value:
                self.feed(node.items, v, f"{where}[]", key)
        elif isinstance(value, str):
            node.types.add("string")
            node.strings += 1
            node.string_formats[string_format(value)] += 1
            if key in LABEL_KEYS:
                node.labels[value] += 1
        elif isinstance(value, bool):
            node.types.add("boolean")
        elif isinstance(value, int):
            node.types.add("integer")
            node.numbers += 1
            node.number_formats[number_format(value)] += 1
        elif isinstance(value, float):
            node.types.add("number")
            node.numbers += 1
            node.number_formats[number_format(value)] += 1
        elif value is None:
            node.types.add("null")

    def label_ok(self, label):
        return (len(label) <= 80 and "@" not in label and not URL.search(label)
                and not re.search(r"\d{3,}", label) and "\n" not in label and not self.values.contains(label))

    def schema(self, node, where):
        types = [t for t in TYPE_ORDER if t in node.types]
        out = {"type": types[0] if len(types) == 1 else types}
        if "object" in node.types:
            literal = {k: v for k, v in node.props.items() if k not in node.patterns}
            if literal:
                out["properties"] = {k: self.schema(v, f"{where}.{k}") for k, v in sorted(literal.items())}
                required = sorted(k for k in literal if node.prop_counts[k] == node.objects)
                if required:
                    out["required"] = required
            if node.patterns:
                out["patternProperties"] = {}
                for name in sorted(node.patterns):
                    sub = self.schema(node.props[name], f"{where}.{name}")
                    sub["x-key-pattern"] = name
                    out["patternProperties"][pattern_regex(name)] = sub
        if "array" in node.types:
            if node.items is not None and node.items.types:
                out["items"] = self.schema(node.items, f"{where}[]")
            else:
                out["x-always-empty"] = True
        if "string" in node.types:
            fmts = set(node.string_formats)
            if len(fmts) == 1 and None not in fmts:
                fmt = fmts.pop()
                out["x-format" if fmt.startswith("x-") else "format"] = fmt.removeprefix("x-")
            if node.labels:
                kept = sorted(l for l in node.labels if self.label_ok(l))
                dropped = sum(1 for l in node.labels if not self.label_ok(l))
                if dropped:
                    self.left_out[f"label not kept (unsure it is the platform's wording): {where}"] += dropped
                if kept:
                    out["enum"] = kept
        if node.numbers:
            fmts = set(node.number_formats)
            if len(fmts) == 1 and None not in fmts:
                out["x-timestamp"] = fmts.pop()
        return out


def pattern_regex(name):
    parts = re.split(r"(<[a-z]+>)", name)
    return "^" + "".join(".+" if PLACEHOLDER.fullmatch(p) else re.escape(p) for p in parts) + "$"


def json_style(raw, decoded_changed):
    text = raw[:4096].decode("utf-8", "replace")
    m = re.search(r"\n( +)\S", text)
    return {"indent": len(m.group(1)) if m else 0, "ascii": all(b < 128 for b in raw),
            "meta_encoding": decoded_changed}


def decode_tree(value):
    """Apply meta_fix to every string and key; report whether anything changed."""
    changed = False

    def walk(v):
        nonlocal changed
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                nk = meta_fix(k)
                changed = changed or nk != k
                out[nk] = walk(x)
            return out
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, str):
            nv = meta_fix(v)
            changed = changed or nv != v
            return nv
        return v

    return walk(value), changed


def extract(zip_path, platform, wording=()):
    """Return a snapshot {platform, files: {pattern: entry}, schemas: {pattern: schema}, left_out}.

    `wording` lists words that are the platform's own even where they also occur as values
    (product names such as "YouTube"); they are kept in file names and keys.
    """
    ex = Extractor(platform, wording)
    archive = zipfile.ZipFile(zip_path)
    names = [i.filename for i in archive.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")
             and not i.filename.rpartition("/")[2].startswith("._") and i.filename.rpartition("/")[2] != ".DS_Store"]
    docs = {}
    csv_heads = {}
    for name in names:
        kind, _ = kind_of(name)
        if kind == "json":
            raw = archive.read(name)
            try:
                tree, changed = decode_tree(json.loads(raw.decode("utf-8-sig")))
            except ValueError:
                docs[name] = None
                continue
            docs[name] = (tree, json_style(raw, changed))
            ex.collect(tree)
        elif kind == "csv":
            text = archive.read(name).decode("utf-8-sig", "replace")
            rows = list(csv.reader(io.StringIO(text)))
            csv_heads[name] = rows[0] if rows else []
            for row in rows[1:]:
                for cell in row:
                    ex.values.add(cell)
    files = {}
    nodes = {}
    styles = {}
    for name in names:
        pattern = path_pattern(name, ex.values, ex.left_out)
        kind, ext = kind_of(name)
        entry = files.setdefault(pattern, {"kind": kind})
        if kind == "json":
            if docs.get(name) is None:
                ex.left_out[f"unreadable JSON: {pattern}"] += 1
                continue
            tree, style = docs[name]
            ex.feed(nodes.setdefault(pattern, Node()), tree, f"{pattern} $")
            styles.setdefault(pattern, style)
        elif kind == "csv":
            columns = []
            for col in csv_heads.get(name, []):
                if ex.label_ok(col) and not PLACEHOLDER.search(id_pattern(col)):
                    columns.append(col)
                else:
                    ex.left_out[f"CSV column name not kept: {pattern}"] += 1
            if "columns" not in entry or len(columns) > len(entry["columns"]):
                entry["columns"] = columns
    schemas = {}
    for pattern, node in nodes.items():
        schema = {"$schema": SCHEMA_DIALECT, "title": pattern}
        schema.update(ex.schema(node, pattern))
        schemas[pattern] = schema
        files[pattern].update(styles[pattern])
    return {"platform": platform, "files": files, "schemas": schemas, "left_out": dict(ex.left_out)}


def package_date(zip_path):
    """The newest entry date in the zip (YYYY-MM-DD), or None when the zip has no real dates."""
    dates = [i.date_time for i in zipfile.ZipFile(zip_path).infolist() if i.date_time[0] > 1980]
    if not dates:
        return None
    y, m, d = max(dates)[:3]
    return f"{y:04d}-{m:02d}-{d:02d}"
