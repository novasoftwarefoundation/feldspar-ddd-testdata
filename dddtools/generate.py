"""Build a synthetic package from a platform's combined structure.

Every file pattern that is still current (not marked "not seen since") becomes
one or more files; every JSON file is filled from its JSON Schema with
synthetic values: required keys always, optional keys often, labels in the
chosen language, timestamps in the year before the export date. The output is
the same for the same structure, options and seed.
"""
import base64
import calendar
import datetime
import json
import random
import zipfile

from .combined import types_of
from .extract import PLACEHOLDER

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==")
JPG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgy"
    "PC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")
WORDS = "synthetic test data sample record value entry text item note example".split()


def meta_encode(text):
    """Write text the way Meta's exports do (UTF-8 bytes read as Latin-1)."""
    return text.encode("utf-8").decode("latin-1")


def meta_tree(value):
    if isinstance(value, dict):
        return {meta_encode(k): meta_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [meta_tree(v) for v in value]
    if isinstance(value, str):
        return meta_encode(value)
    return value


class Generator:
    def __init__(self, combined, seed=1, records=5, lang=None, date=None, instances=2, include_old=False):
        self.c = combined
        self.r = random.Random(seed)
        self.records = records
        self.lang = lang
        self.instances = instances
        self.include_old = include_old
        last = date or max((p["date"] for p in combined.meta["packages"]), default="2026-01-01")
        self.date = datetime.date.fromisoformat(last)
        self.end = calendar.timegm(self.date.timetuple())
        self.counter = 0

    def fill(self, placeholder_pattern, index=0):
        def sub(m):
            self.counter += 1
            n = self.counter
            return {
                "<name>": f"synthetic_user{n}", "<id>": f"{1000000 + n}", "<n>": str(index + 1), "<hex>": f"{n:032x}",
                "<uuid>": f"00000000-0000-4000-8000-{n:012x}", "<yyyymm>": self.date.strftime("%Y%m"),
                "<yyyymmdd>": self.date.strftime("%Y%m%d"), "<value>": f"synthetic{n}",
                "<email>": f"user{n}@example.com", "<url>": f"https://example.com/{n}",
                "<text>": "Synthetic text, long enough to stand for free text that the extractor leaves out " * 2,
            }.get(m.group(0), f"x{n}")

        return PLACEHOLDER.sub(sub, placeholder_pattern)

    def timestamp(self):
        return self.end - self.r.randrange(365 * 86400)

    def value(self, schema):
        types = types_of(schema) or ["null"]
        concrete = [t for t in types if t != "null"]
        if not concrete or ("null" in types and self.r.random() < 0.1):
            return None
        kind = concrete[0] if len(concrete) == 1 else self.r.choice(concrete)
        if kind == "object":
            out = {}
            required = set(schema.get("required", []))
            for key, sub in schema.get("properties", {}).items():
                if sub.get("x-not-seen-since") and not self.include_old:
                    continue
                if key in required or self.r.random() < 0.7:
                    out[key] = self.value(sub)
            for sub in schema.get("patternProperties", {}).values():
                for _ in range(min(2, self.records)):
                    out[self.fill(sub.get("x-key-pattern", "<value>"))] = self.value(sub)
            return out
        if kind == "array":
            if "items" not in schema:
                return []
            return [self.value(schema["items"]) for _ in range(self.r.randint(1, self.records))]
        if kind == "string":
            return self.string(schema)
        if kind == "integer":
            unit = schema.get("x-timestamp")
            if unit == "unix-seconds":
                return self.timestamp()
            if unit == "unix-milliseconds":
                return self.timestamp() * 1000 + self.r.randrange(1000)
            return self.r.randrange(1000)
        if kind == "number":
            unit = schema.get("x-timestamp")
            if unit == "unix-seconds":
                return self.timestamp() + round(self.r.random(), 6)
            if unit == "unix-milliseconds":
                return float(self.timestamp() * 1000)
            return round(self.r.random() * 100, 3)
        if kind == "boolean":
            return self.r.random() < 0.5
        return None

    def string(self, schema):
        if "enum" in schema:
            labels = schema["enum"]
            info = schema.get("x-labels", {})
            if self.lang:
                in_lang = [l for l in labels if self.lang in info.get(l, {}).get("langs", [self.lang])]
                labels = in_lang or labels
            return self.r.choice(labels)
        fmt = schema.get("format") or schema.get("x-format")
        ts = datetime.datetime.fromtimestamp(self.timestamp(), datetime.timezone.utc)
        self.counter += 1
        if fmt == "date-time":
            return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if fmt == "local-date-time":
            return ts.strftime("%Y-%m-%d %H:%M:%S")
        if fmt == "date":
            return ts.strftime("%Y-%m-%d")
        if fmt == "uri":
            return f"https://example.com/synthetic/{self.counter}"
        if fmt == "email":
            return f"user{self.counter}@example.com"
        # Always two words or more, so a value never equals a key or a file name.
        return "Synthetic " + " ".join(self.r.choice(WORDS) for _ in range(self.r.randint(1, 6)))

    def file_bytes(self, pattern, entry):
        kind = entry["kind"]
        if kind == "json":
            schema = self.c.schemas.get(pattern)
            tree = self.value(schema) if schema else {}
            if entry.get("meta_encoding"):
                tree = meta_tree(tree)
            indent = entry.get("indent") or None
            return json.dumps(tree, indent=indent, ensure_ascii=bool(entry.get("ascii", True))).encode()
        if kind == "csv":
            columns = entry.get("columns", [])
            rows = [",".join(columns)] + [",".join(f"synthetic {i}" for _ in columns) for i in range(self.records)]
            return ("\n".join(rows) + "\n").encode()
        if kind == "html":
            return b"<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body><p>Synthetic</p></body></html>\n"
        ext = pattern.rpartition(".")[2].lower()
        if ext == "png":
            return PNG
        if ext in ("jpg", "jpeg"):
            return JPG
        return b"synthetic placeholder\n"

    def build(self, output):
        stamp = (self.date.year, self.date.month, self.date.day, 12, 0, 0)
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for pattern in sorted(self.c.meta["files"]):
                entry = self.c.meta["files"][pattern]
                if entry.get("not_seen_since") and not self.include_old:
                    continue
                copies = self.instances if PLACEHOLDER.search(pattern) else 1
                for index in range(copies):
                    info = zipfile.ZipInfo(self.fill(pattern, index), stamp)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, self.file_bytes(pattern, entry))
        return output

