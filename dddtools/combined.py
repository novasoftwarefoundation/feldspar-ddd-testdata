"""The combined structure of a platform: everything seen in any package added so far.

Layout of structures/<platform>/:
  files.yaml          one entry per file pattern, with seen-in count, first and last export date
  schemas/*.schema.json   one JSON Schema (draft 2020-12) per JSON file pattern
  LIMITS.md           coverage, what was left out, known gaps and the last change

Bookkeeping lives in `x-` keywords that standard JSON Schema tools ignore:
x-seen-in, x-first-seen, x-last-seen, x-langs, x-not-seen-since and x-changes.
A part is marked "not seen since" only when a newer package in one of its languages lacks it.
"""
import copy
import json
import os
import re

from . import yamlio
from .extract import TYPE_ORDER, pattern_regex

FILES_HEADER = """Layout of {platform} packages, combined over every package added with `ddd.py add`.
Written by ddd.py; only `expected`, `wording` and `notes` are edited by hand:
  expected: file names the platform's donation scripts read (alternatives separated by " | ")
  wording: the platform's own words that also occur as values, kept in names and keys"""


def types_of(schema):
    t = schema.get("type", [])
    return [t] if isinstance(t, str) else list(t)


def shape(schema):
    """Types plus timestamp unit, e.g. ['integer:unix-seconds', 'null']."""
    out = []
    for t in types_of(schema):
        if t in ("integer", "number") and schema.get("x-timestamp"):
            out.append(f"{t}:{schema['x-timestamp']}")
        else:
            out.append(t)
    return out


def set_types(schema, types):
    ordered = [t for t in TYPE_ORDER if t in types]
    schema["type"] = ordered[0] if len(ordered) == 1 else ordered


def children(schema):
    """(kind, name, child) for every sub-schema: properties, patternProperties and items."""
    for name, child in schema.get("properties", {}).items():
        yield "properties", name, child
    for regex, child in schema.get("patternProperties", {}).items():
        yield "patternProperties", regex, child
    if "items" in schema:
        yield "items", None, schema["items"]


def label_of(kind, name, child):
    if kind == "items":
        return "[]"
    if kind == "patternProperties":
        return "." + child.get("x-key-pattern", name)
    return "." + name


def stamp(schema, date, lang):
    """Mark a fresh schema (and everything below it) as seen once, on `date`."""
    schema["x-seen-in"] = 1
    schema["x-first-seen"] = date
    schema["x-last-seen"] = date
    schema["x-langs"] = [lang]
    if "enum" in schema:
        schema["x-labels"] = {l: {"seen-in": 1, "first-seen": date, "last-seen": date, "langs": [lang]}
                              for l in schema["enum"]}
    for _, _, child in children(schema):
        stamp(child, date, lang)
    return schema


def merge(old, new, date, lang, path, changes):
    """Merge a package's schema `new` into the combined schema `old` in place."""
    newer = date >= old["x-last-seen"]
    old["x-seen-in"] += 1
    old["x-first-seen"] = min(old["x-first-seen"], date)
    old["x-langs"] = sorted(set(old.get("x-langs", [])) | {lang})
    if newer:
        old["x-last-seen"] = date
        old.pop("x-not-seen-since", None)
    old_shape, new_shape = shape(old), shape(new)
    if not set(new_shape) <= set(old_shape):
        old.setdefault("x-changes", []).append({"date": date, "from": old_shape, "to": new_shape})
        changes.append(f"~ {path}: {' | '.join(old_shape)} -> {' | '.join(new_shape)}")
        set_types(old, set(types_of(old)) | set(types_of(new)))
        if old.get("x-timestamp") != new.get("x-timestamp"):
            old.pop("x-timestamp", None)
    for key in ("format", "x-format"):
        if old.get(key) != new.get(key):
            old.pop(key, None)
    if new.get("x-always-empty") is None:
        old.pop("x-always-empty", None)
    if "enum" in new:
        labels = old.setdefault("x-labels", {})
        for label in new["enum"]:
            if label in labels:
                info = labels[label]
                info["seen-in"] += 1
                info["first-seen"] = min(info["first-seen"], date)
                info["last-seen"] = max(info["last-seen"], date)
                if lang not in info["langs"]:
                    info["langs"] = sorted(info["langs"] + [lang])
            else:
                labels[label] = {"seen-in": 1, "first-seen": date, "last-seen": date, "langs": [lang]}
                changes.append(f"+ {path}: label {json.dumps(label, ensure_ascii=False)}")
        old["enum"] = sorted(labels)
    for kind in ("properties", "patternProperties"):
        if kind not in old and kind not in new:
            continue
        olds = old.setdefault(kind, {})
        news = new.get(kind, {})
        for name in sorted(set(olds) | set(news)):
            label = label_of(kind, name, olds.get(name) or news.get(name))
            if name in olds and name in news:
                merge(olds[name], news[name], date, lang, path + label, changes)
            elif name in news:
                olds[name] = stamp(copy.deepcopy(news[name]), date, lang)
                changes.append(f"+ {path}{label}")
            elif (newer and "object" in types_of(new) and "x-not-seen-since" not in olds[name]
                  and lang in olds[name].get("x-langs", [lang])):
                # Only a newer package in the same language counts: Meta writes keys in the user's language.
                olds[name]["x-not-seen-since"] = olds[name]["x-last-seen"]
                changes.append(f"- {path}{label} (not seen since {olds[name]['x-last-seen']})")
    if "properties" in old:
        old_required = set(old.get("required", []))
        new_required = set(new.get("required", [])) if "object" in types_of(new) else old_required
        required = sorted(old_required & new_required)
        if required:
            old["required"] = required
        else:
            old.pop("required", None)
    if "items" in new:
        if "items" in old:
            merge(old["items"], new["items"], date, lang, path + "[]", changes)
        else:
            old["items"] = stamp(copy.deepcopy(new["items"]), date, lang)
            changes.append(f"+ {path}[] (first non-empty list)")


def schema_file(pattern):
    """schemas/<pattern>.schema.json, with <placeholder> written as {placeholder}."""
    stem = re.sub(r"<([a-z]+)>", r"{\1}", pattern)
    stem = stem[: -len(".json")] if stem.endswith(".json") else stem
    return f"schemas/{stem}.schema.json"


class Combined:
    def __init__(self, folder, platform=None):
        self.folder = folder
        path = os.path.join(folder, "files.yaml")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.meta = yamlio.loads(f.read())
        else:
            self.meta = {"platform": platform or os.path.basename(os.path.normpath(folder)), "packages": [],
                         "files": {}, "left_out": {}, "expected": [], "wording": [], "notes": []}
        self.meta.setdefault("files", {})
        self.meta.setdefault("left_out", {})
        self.meta.setdefault("expected", [])
        self.meta.setdefault("packages", [])
        self.meta.setdefault("notes", [])
        self.meta.setdefault("wording", [])
        self.schemas = {}
        for pattern, entry in self.meta["files"].items():
            if entry.get("schema"):
                with open(os.path.join(folder, entry["schema"]), encoding="utf-8") as f:
                    self.schemas[pattern] = json.load(f)

    @property
    def platform(self):
        return self.meta["platform"]

    def add(self, snapshot, date, lang):
        """Merge one package snapshot. Returns the list of changes, one line each."""
        changes = []
        files = self.meta["files"]
        for pattern in sorted(set(files) | set(snapshot["files"])):
            new = snapshot["files"].get(pattern)
            old = files.get(pattern)
            if new and not old:
                entry = {k: v for k, v in new.items()}
                entry.update({"seen_in": 1, "first_seen": date, "last_seen": date, "langs": [lang]})
                if pattern in snapshot["schemas"]:
                    entry["schema"] = schema_file(pattern)
                    self.schemas[pattern] = stamp(copy.deepcopy(snapshot["schemas"][pattern]), date, lang)
                files[pattern] = entry
                changes.append(f"+ file {pattern}")
            elif new and old:
                newer = date >= old["last_seen"]
                old["seen_in"] += 1
                old["first_seen"] = min(old["first_seen"], date)
                old["langs"] = sorted(set(old.get("langs", [])) | {lang})
                if newer:
                    old["last_seen"] = date
                    old.pop("not_seen_since", None)
                if old["kind"] != new["kind"]:
                    changes.append(f"~ file {pattern}: {old['kind']} -> {new['kind']}")
                    old.setdefault("changes", []).append({"date": date, "from": old["kind"], "to": new["kind"]})
                    old["kind"] = new["kind"]
                for key in ("columns",):
                    if key in new and new[key] != old.get(key):
                        if key in old:
                            changes.append(f"~ file {pattern}: columns changed")
                            old.setdefault("changes", []).append({"date": date, "from": old[key], "to": new[key]})
                        old[key] = new[key]
                for key in ("indent", "ascii"):
                    if key in new and newer:
                        old[key] = new[key]
                if "meta_encoding" in new:
                    old["meta_encoding"] = bool(old.get("meta_encoding")) or new["meta_encoding"]
                if pattern in snapshot["schemas"]:
                    if pattern in self.schemas:
                        merge(self.schemas[pattern], snapshot["schemas"][pattern], date, lang, pattern, changes)
                    else:
                        old["schema"] = schema_file(pattern)
                        self.schemas[pattern] = stamp(copy.deepcopy(snapshot["schemas"][pattern]), date, lang)
                        changes.append(f"+ schema {pattern}")
            elif (old and not new and date > old["last_seen"] and "not_seen_since" not in old
                  and lang in old.get("langs", [lang])):
                old["not_seen_since"] = old["last_seen"]
                changes.append(f"- file {pattern} (not seen since {old['last_seen']})")
        for where, count in snapshot["left_out"].items():
            self.meta["left_out"][where] = self.meta["left_out"].get(where, 0) + count
        self.meta["packages"] = sorted(self.meta["packages"] + [{"date": date, "lang": lang}],
                                       key=lambda p: (p["date"], p["lang"]))
        added = sum(1 for c in changes if c.startswith("+"))
        removed = sum(1 for c in changes if c.startswith("-"))
        changed = sum(1 for c in changes if c.startswith("~"))
        self.meta["last_change"] = {
            "date": date,
            "summary": f"package of {date} ({lang}) added: {added} new, {changed} changed shape, "
                       f"{removed} not seen since an earlier package",
        }
        return changes

    def save(self):
        os.makedirs(os.path.join(self.folder, "schemas"), exist_ok=True)
        for pattern, schema in self.schemas.items():
            path = os.path.join(self.folder, self.meta["files"][pattern]["schema"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(sort_schema(schema), indent=2, ensure_ascii=False) + "\n")
        with open(os.path.join(self.folder, "files.yaml"), "w", encoding="utf-8") as f:
            f.write(yamlio.dumps(self.meta, FILES_HEADER.format(platform=self.platform)))
        write_limits(self)


def sort_schema(value):
    """Stable key order: $schema, title and type first, then the rest sorted."""
    if isinstance(value, dict):
        head = [k for k in ("$schema", "title", "type") if k in value]
        return {k: sort_schema(value[k]) for k in head + sorted(k for k in value if k not in head)}
    if isinstance(value, list):
        return [sort_schema(v) for v in value]
    return value


def walk(schema, path):
    yield path, schema
    for kind, name, child in children(schema):
        yield from walk(child, path + label_of(kind, name, child))


def expected_seen(expected, patterns):
    """`expected` is a file name, or alternatives separated by " | "."""
    regexes = [re.compile(pattern_regex(p.rpartition("/")[2])) for p in patterns]
    return any(r.match(name.strip().rpartition("/")[2]) for name in expected.split("|") for r in regexes)


HAND_START = "<!-- known gaps by hand: start -->"
HAND_END = "<!-- known gaps by hand: end -->"


def write_limits(combined):
    meta = combined.meta
    path = os.path.join(combined.folder, "LIMITS.md")
    hand = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if HAND_START in text and HAND_END in text:
            hand = text.split(HAND_START, 1)[1].split(HAND_END, 1)[0].strip("\n")
    packages = meta["packages"]
    dates = sorted({p["date"] for p in packages})
    langs = sorted({p["lang"] for p in packages})
    files = meta["files"]
    kinds = {}
    for entry in files.values():
        kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
    empty = []
    for pattern, schema in sorted(combined.schemas.items()):
        for where, node in walk(schema, ""):
            if node.get("x-always-empty"):
                empty.append(f"{pattern} {where or '$'}")
    missing = [e for e in meta["expected"] if not expected_seen(e, files)]
    gone = sorted(f"{p} (not seen since {e['not_seen_since']})" for p, e in files.items() if e.get("not_seen_since"))
    lines = [f"# {meta['platform']}: limits of the known structure", "",
             "A structure is only as complete as the packages it came from: a file, key or label that no package "
             "has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "
             "\"by hand\" markers is kept.", "", "## Coverage", ""]
    lines.append(f"- Packages: {len(packages)}" + (f", export dates {', '.join(dates)}; languages {', '.join(langs)}"
                                                  if packages else ""))
    lines.append(f"- File patterns seen: {len(files)} (" + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
                 + ")")
    if not any(e["kind"] == "media" for e in files.values()):
        lines.append("- No media files (photos, videos, audio) in any package yet.")
    lines.append(f"- Lists that were empty in every package, so their items are unknown: {len(empty)}")
    lines += [f"  - `{e}`" for e in empty]
    lines += ["", "## Left out", "",
              "Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or "
              "dropped; only the place and the count are kept.", ""]
    if meta["left_out"]:
        lines += [f"- {count} × {where}" for where, count in sorted(meta["left_out"].items())]
    else:
        lines.append("- Nothing.")
    lines += ["", "## Known gaps", "",
              f"Files the platform's donation scripts read that no package has shown yet: {len(missing)}"]
    lines += [f"- `{m}`" for m in missing]
    if gone:
        lines += ["", "Files that newer packages no longer have:"] + [f"- `{g}`" for g in gone]
    lines += ["", HAND_START, hand, HAND_END, "", "## Last change", ""]
    if meta.get("last_change"):
        lines.append(f"- {meta['last_change']['date']}: {meta['last_change']['summary']}")
    else:
        lines.append("- None yet.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).replace("\n\n\n", "\n\n") + "\n")


def _match(name, patterns):
    """The pattern in `patterns` that `name` is an instance of (itself, or a placeholder pattern)."""
    if name in patterns:
        return name
    for pattern in patterns:
        if re.match(pattern_regex(pattern), name):
            return pattern
    return None


def compare(a, b, check=False):
    """Differences between two snapshots or combined structures: files, keys, types and labels.

    With check, only what `b` has that `a` doesn't know is reported: a part `b` lacks, or a
    narrower type in `b`, is no difference.
    """
    out = []
    fa, fb = a["files"], b["files"]
    matched = {p: _match(p, fa) for p in fb}
    for pattern in sorted(set(fa) | set(fb)):
        if pattern in fb and matched[pattern] is None:
            out.append(f"+ file {pattern}")
        elif pattern not in fb:
            if not check and pattern not in matched.values():
                out.append(f"- file {pattern}")
        else:
            known = matched[pattern]
            ea, eb = fa[known], fb[pattern]
            if ea["kind"] != eb["kind"]:
                out.append(f"~ file {pattern}: {ea['kind']} -> {eb['kind']}")
            if "columns" in eb and ea.get("columns") != eb["columns"]:
                if not check or set(eb["columns"]) - set(ea.get("columns", [])):
                    out.append(f"~ file {pattern}: columns {ea.get('columns')} -> {eb['columns']}")
            sa, sb = a["schemas"].get(known), b["schemas"].get(pattern)
            if sa and sb:
                compare_schema(sa, sb, pattern, out, check)
    return out


def _names(schema):
    names = {k: ("properties", k) for k in schema.get("properties", {})}
    for regex, sub in schema.get("patternProperties", {}).items():
        names[sub.get("x-key-pattern", regex)] = ("patternProperties", regex)
    return names


def compare_schema(a, b, path, out, check=False):
    if set(shape(b)) - set(shape(a)) or (not check and set(shape(a)) != set(shape(b))):
        out.append(f"~ {path}: {' | '.join(shape(a))} -> {' | '.join(shape(b))}")
    la, lb = set(a.get("enum", [])), set(b.get("enum", []))
    for label in sorted(lb - la):
        out.append(f"+ {path}: label {json.dumps(label, ensure_ascii=False)}")
    if not check:
        for label in sorted(la - lb):
            out.append(f"- {path}: label {json.dumps(label, ensure_ascii=False)}")
    names_a, names_b = _names(a), _names(b)
    seen = set()
    for name in sorted(names_b):
        known = _match(name, names_a)
        if known is None:
            out.append(f"+ {path}.{name}")
            continue
        seen.add(known)
        (kind_a, key_a), (kind_b, key_b) = names_a[known], names_b[name]
        compare_schema(a[kind_a][key_a], b[kind_b][key_b], f"{path}.{name}", out, check)
    if not check:
        for name in sorted(set(names_a) - seen):
            out.append(f"- {path}.{name}")
    if "items" in a and "items" in b:
        compare_schema(a["items"], b["items"], path + "[]", out, check)
    elif "items" in b:
        out.append(f"+ {path}[]")


def as_snapshot(combined):
    return {"platform": combined.platform, "files": combined.meta["files"], "schemas": combined.schemas}
