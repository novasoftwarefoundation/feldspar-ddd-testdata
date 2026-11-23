"""Rebuild the Google stress zip from the anonymized google-full, with exactly the original's entry list.

    python3 stress_build.py <stress-original.zip> <google-full-original.zip> <google-full-anonymized.zip> <out.zip>

Every data file of the stress zip must be byte-identical to the google-full file it copies (checked);
it is replaced by that file's anonymized version. Folders, .DS_Store files (Finder layout + the archive's
own names) and __MACOSX AppleDouble files (quarantine flags/time, last-used date) are kept, except a
com.apple.macl value (machine-specific ids), whose bytes are replaced by random bytes of the same length.
Prints counts only.
"""
import collections
import os
import re
import struct
import sys
import zipfile

stress_p, full_o_p, full_a_p, out_p = sys.argv[1:5]
stress, full_o, full_a = zipfile.ZipFile(stress_p), zipfile.ZipFile(full_o_p), zipfile.ZipFile(full_a_p)
orig_bytes = {i.filename: full_o.read(i) for i in full_o.infolist() if not i.is_dir()}
anon_bytes = {i.filename: full_a.read(i) for i in full_a.infolist() if not i.is_dir()}
assert orig_bytes.keys() == anon_bytes.keys()


def base(n):
    """'Takeout/Mijn activiteit copy 12/x.json' -> 'Takeout/Mijn activiteit/x.json'; also ' copy' without a
    number and before an extension ('archive_browser copy.html')."""
    return re.sub(r" copy(?: \d+)?(?=/|\.\w+$|$)", "", n)


def scrub_macl(d):
    """Overwrite the value of a com.apple.macl attribute in an AppleDouble file with random bytes."""
    a = d.find(b"ATTR")
    if a < 0:
        return d, 0
    num = struct.unpack(">H", d[a + 34:a + 36])[0]
    pos, out, n = a + 36, bytearray(d), 0
    for _ in range(num):
        off, length, _flags, nlen = struct.unpack(">IIHB", d[pos:pos + 11])
        name = d[pos + 11:pos + 11 + nlen].rstrip(b"\x00")
        if name == b"com.apple.macl":
            out[off:off + length] = os.urandom(length)
            n += 1
        pos = (pos + 11 + nlen + 3) & ~3
    return bytes(out), n


stats = collections.Counter()
with zipfile.ZipFile(out_p, "w") as zout:
    for i in stress.infolist():
        if i.is_dir():
            body = b""
            stats["folder"] += 1
        elif i.filename.startswith("__MACOSX/"):
            body, n = scrub_macl(stress.read(i))
            stats["AppleDouble (macl scrubbed)" if n else "AppleDouble kept"] += 1
        elif i.filename.endswith(".DS_Store"):
            body = stress.read(i)
            stats[".DS_Store kept"] += 1
        else:
            b = base(i.filename)
            if b not in orig_bytes:
                raise SystemExit("a data file without a google-full counterpart; stopping")
            if stress.read(i) != orig_bytes[b]:
                raise SystemExit("a data file differs from its google-full counterpart; stopping")
            body = anon_bytes[b]
            stats["data file from anonymized google-full"] += 1
        zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
        zi.compress_type = i.compress_type
        zi.external_attr = i.external_attr
        zi.create_system = i.create_system
        zi.create_version = i.create_version
        zi.extract_version = i.extract_version
        zi.flag_bits = i.flag_bits & ~0x08
        zi.extra = i.extra
        zout.writestr(zi, body)
print(dict(stats))
