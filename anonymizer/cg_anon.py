"""Anonymize the ChatGPT error-case exports, keeping each file's deliberate breakage byte for byte.

    python3 cg_anon.py <out-dir> <zip> [<zip> ...]      (all in one run: one mapping for all of them)

Each copy gets the same file name as its original, in <out-dir>; an existing file is never replaced.

JSON-ish files (also when they don't parse, and the data embedded in chat.html) are rewritten string literal
by string literal: every byte outside a literal's contents stays as it was, so structure, whitespace and any
breakage are kept. Ids (UUIDs, file ids, user ids, digests) map the same way in every file, key and entry
name. Attachments become tiny placeholders of the same type. Prints counts only.
"""
import collections
import io
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
import anonymize as an  # noqa: E402

STATS, UNSURE = collections.Counter(), collections.Counter()
LIT = re.compile(r'"(?:[^"\\\n]|\\.)*"')
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
FILEID = re.compile(r"(file[-_])([A-Za-z0-9]{10,})")
USERID = re.compile(r"(user-)([A-Za-z0-9]{10,})")
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
KEEP = {"content_type", "default_model_slug", "model_slug", "role", "source", "type", "ref_type", "render_format",
        "inline_reference_type", "memory_scope", "create_time", "update_time", "mime_type",
        "content_backing_kind", "file_name_provenance", "state", "library_artifact_type", "library_artifact_subtype",
        "library_file_category", "file_extension", "version_provenance", "deletion_origin", "deletion_reason",
        "calpico_who_can_message_me", "created_at", "updated_at", "modified_at", "file_processed_time",
        "file_upload_time", "last_used_at", "metadata_updated_at", "record_creation_time", "version_created_at",
        "pinned_at", "trashed_at", "user_renamed_at", "deleted_at", "expires_at", "file_failure_time", "status",
        "recipient", "channel", "finish_details", "stop_tokens", "voice", "gizmo_type"}
TEXT = {"title", "parts", "content", "alt", "snippet", "summary", "prompt_text", "symbol", "text", "attribution",
        "error_msg", "query", "queries", "user_profile", "user_instructions", "about_user_message", "about_model_message"}
NAMES = {"name", "file_name", "normalized_name"}
URLS = {"tool_icons", "logo", "icon", "url", "thumbnail_url", "source_url", "cloud_doc_url", "source_icon_url", "journal_homepage_url", "link"}
EMAILS = {"email"}
IDS = {"id", "parent", "current_node", "conversation_id", "message_id", "parent_id", "source_analysis_msg_id",
       "image_send_uuid", "library_file_id", "image_prompt_id", "directory_id", "etag", "partition_key", "file_id",
       "uploading_account_user_id", "origination_message_id", "origination_thread_id", "root_directory_id",
       "knowledge_store_id", "app_id", "sha256_digest", "client_sha256_digest", "legacy_retrieval_document_id",
       "rehomed_to_library_file_id", "trash_original_directory_id", "image_gen_generation_id", "request_id",
       "asset_pointer", "path", "files", "children", "conversation_template_id", "gizmo_id"}
OPENAI_HOSTS = re.compile(r"(^|\.)(openai\.com|chatgpt\.com|oaiusercontent\.com|oaistatic\.com)$")


def hexmap(s, kind):
    r = an.rng_for(kind, s)
    return "".join(r.choice("0123456789abcdef") if c in "0123456789abcdef" else c for c in s)


def ids_in(s):
    """Map every id inside s; the same id gets the same new id in every file."""
    s = UUID.sub(lambda m: hexmap(m.group(), "uuid"), s)
    s = HEX64.sub(lambda m: hexmap(m.group(), "digest"), s)
    s = FILEID.sub(lambda m: m.group(1) + (hexmap(m.group(2), "fid") if re.fullmatch(r"[0-9a-f]+", m.group(2))
                                           else an.scramble_ident(m.group(2), "fid")), s)
    s = USERID.sub(lambda m: m.group(1) + an.scramble_ident(m.group(2), "uid"), s)
    return s


def has_id(s):
    return bool(UUID.search(s) or FILEID.search(s) or USERID.search(s) or HEX64.search(s))


def cg_url(u):
    try:
        from urllib.parse import urlsplit, urlunsplit
        p = urlsplit(u)
    except ValueError:
        return an.scramble_ident(u, "url")
    host = p.hostname or ""
    if OPENAI_HOSTS.search(host):
        netloc = p.netloc
    else:
        netloc = an.fake_netloc(p.netloc, host)
    path = "/".join(ids_in(x) if has_id(x) else an.scramble_ident(x, "seg") for x in p.path.split("/"))
    query = "&".join((kv.split("=", 1)[0] + "=" + an.scramble_ident(kv.split("=", 1)[1], "q")) if "=" in kv else kv
                     for kv in p.query.split("&")) if p.query else ""
    return urlunsplit((p.scheme, netloc, path, query, an.scramble_ident(p.fragment, "f") if p.fragment else ""))


an.fake_url = cg_url


def fake_filename(v):
    m = re.fullmatch(r"(.*?)(\.[A-Za-z0-9]{1,6})", v)
    return (an.apply("text", m.group(1), "file name") + m.group(2)) if m and m.group(1) else an.apply("text", v, "file name")


def value(v, key, strict):
    if v == "" or re.fullmatch(r"[\d\-: T.+Z]+", v):
        return v
    if key is not None and (has_id(key) or re.search(r"\d{6,}", key)):
        key = "<id-key>"          # a key that is itself data (an id): never printed, handled by the value
    if key in ("path", "files", "manifest_file"):     # export file names: only the ids in them change
        STATS[("path (ids only)", key)] += 1
        return ids_in(v)
    if key in IDS or (has_id(v) and key not in TEXT):
        if re.fullmatch(r"[a-z][a-z\-]+", v):          # e.g. "client-created-root"
            return v
        STATS[("id", key)] += 1
        return ids_in(v) if has_id(v) else an.apply("id", v, key)
    if strict:
        STATS[("text (attachment)", "value")] += 1
        return an.apply("text", v, "attachment")
    if key in KEEP:
        STATS[("keep", key)] += 1
        return v
    if key in EMAILS:
        STATS[("email", key)] += 1
        return an.apply("email", v, key)
    if key in URLS or (key in TEXT and re.fullmatch(r"https?://\S+", v)):
        STATS[("url", key)] += 1
        return an.apply("url", v, key)
    if key == "domain":
        STATS[("domain", key)] += 1
        return an.apply("header", v, key)
    if key in NAMES:
        if re.search(r"\.[A-Za-z0-9]{1,6}$", v):
            STATS[("file name", key)] += 1
            return fake_filename(v)
        if re.fullmatch(r"[a-z0-9_.]+", v):            # a tool / plugin name such as "web.run"
            STATS[("keep (tool name)", key)] += 1
            return v
        STATS[("text", key)] += 1
        return an.apply("text", v, key)
    if key in TEXT:
        STATS[("text", key)] += 1
        return an.apply("text", v, key)
    if re.fullmatch(r"[a-z_]{1,40}", v):
        STATS[("keep (enum-like, unknown key)", key)] += 1
        return v
    UNSURE[key] += 1
    STATS[("text (unknown key)", key)] += 1
    return an.apply("text", v, key)


def rewrite(raw, strict=False, span=None):
    """Rewrite the JSON string literals of raw (optionally only within span); all other bytes stay."""
    out, pos, key = [], 0, None
    lo, hi = span or (0, len(raw))
    for m in LIT.finditer(raw, lo, hi):
        lit = m.group()
        try:
            s = json.loads(lit)
        except ValueError:
            continue
        j = m.end()
        while j < len(raw) and raw[j] in " \t\r\n":
            j += 1
        is_key = j < len(raw) and raw[j] == ":"
        if is_key:
            new = ids_in(s) if has_id(s) else s
            if new != s:
                STATS[("id", "<key>")] += 1
            key = s
        else:
            new = value(s, key, strict)
        if new != s:
            ascii_style = "\\u" in lit
            enc = json.dumps(new, ensure_ascii=ascii_style)
            out.append(raw[pos:m.start()])
            out.append(enc)
            pos = m.end()
    out.append(raw[pos:])
    return "".join(out)


def literals(raw, span=None):
    lo, hi = span or (0, len(raw))
    res = []
    for m in LIT.finditer(raw, lo, hi):
        try:
            res.append(json.loads(m.group()))
        except ValueError:
            pass
    return res


def html_spans(h):
    spans = []
    for var in ("jsonData", "assetsJson"):
        i = h.find("var " + var + " = ")
        if i >= 0:
            start = i + len("var " + var + " = ")
            _, end = json.JSONDecoder().raw_decode(h, start)
            spans.append((start, end))
    return spans


def placeholder(d, ph):
    if d[:4] == b"\x89PNG":
        return ph["png"]
    if d[8:12] == b"WEBP":
        return ph["webp"]
    if d[:4] == b"%PDF":
        return ph["pdf"]
    if d[:3] == b"\xff\xd8\xff":
        return ph["jpg"]
    return None


def make_placeholders():
    from PIL import Image
    ph = {}
    for fmt, key in (("PNG", "png"), ("WEBP", "webp"), ("JPEG", "jpg")):
        b = io.BytesIO()
        Image.new("RGB", (8, 8), (128, 128, 128)).save(b, fmt)
        ph[key] = b.getvalue()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>"]
    pdf, offs = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offs.append(len(pdf))
        pdf += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    x = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    ph["pdf"] = bytes(pdf)
    return ph


def main(outdir, paths):
    ph = make_placeholders()
    zips = [zipfile.ZipFile(p) for p in paths]
    # every original string of every file: fakes must never equal one, nor bring in one of their tokens
    for z in zips:
        for i in z.infolist():
            if i.filename.endswith((".json", ".html")) or z.read(i)[:1] in (b"[", b"{"):
                raw = z.read(i).decode("utf-8", "replace")
                for s in literals(raw):
                    an._all_strings(s)
    taken = {t for t in an.ORIG_TOKENS}
    for n in list(an.BY_LEN):
        an.BY_LEN[n] = [w for w in an.BY_LEN[n] if w.casefold() not in taken] or an.BY_LEN[n]
    for p, z in zip(paths, zips):
        out = os.path.join(outdir, os.path.basename(p))
        kinds = collections.Counter()
        with zipfile.ZipFile(out, "x") as zout:
            for i in z.infolist():
                d = z.read(i)
                name = ids_in(i.filename)
                if i.filename == "user.json":
                    t = rewrite(d.decode("utf-8"))
                    t = re.sub(r'("birth_year":\s*)(\d{4})', lambda m: m.group(1) + str(1975 + an.rng_for("by", m.group(2)).randrange(25)), t)
                    body = t.encode("utf-8")
                    kinds["user.json"] += 1
                elif i.filename.endswith(".html"):
                    h = d.decode("utf-8")
                    spans = html_spans(h)
                    for span in reversed(spans):
                        h = h[:span[0]] + rewrite(h[:span[1]], span=span)[span[0]:] + h[span[1]:]
                    # ids (file names of the attachments) also occur in the page around the data: map them there too
                    spans = html_spans(h)
                    pieces, last = [], 0
                    for a, b in spans:
                        pieces.append(ids_in(h[last:a]))
                        pieces.append(h[a:b])
                        last = b
                    pieces.append(ids_in(h[last:]))
                    h = "".join(pieces)
                    body = h.encode("utf-8")
                    kinds["html (embedded data rewritten)"] += 1
                elif i.filename.endswith(".json"):
                    body = rewrite(d.decode("utf-8")).encode("utf-8")
                    kinds["json (literal rewrite)"] += 1
                else:
                    body = placeholder(d, ph)
                    if body is None and d[:1] in (b"[", b"{"):
                        body = rewrite(d.decode("utf-8"), strict=True).encode("utf-8")
                        kinds["json attachment (all values replaced)"] += 1
                    elif body is None:
                        raise SystemExit("unknown attachment type; stopping")
                    else:
                        kinds["attachment placeholder"] += 1
                zi = zipfile.ZipInfo(name, date_time=i.date_time)
                zi.compress_type = i.compress_type
                zi.external_attr = i.external_attr
                zi.create_system = i.create_system
                zout.writestr(zi, body)
        print(os.path.basename(out), dict(kinds))
    for (k, f), n in sorted(STATS.items()):
        print(f"   {k} | {f}: {n}")
    print("unsure keys (replaced as text):", dict(UNSURE) or "none")
    print("fake collisions:", dict(an.COLLISIONS) or "none")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
