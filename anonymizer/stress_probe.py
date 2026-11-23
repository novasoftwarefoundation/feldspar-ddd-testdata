"""Probe the Google stress zip against google-full. Counts, masked names and xattr names only."""
import collections
import hashlib
import re
import struct
import sys
import zipfile

stress = zipfile.ZipFile(sys.argv[1])
full = zipfile.ZipFile(sys.argv[2])
fhash = {i.filename: hashlib.sha256(full.read(i)).hexdigest() for i in full.infolist() if not i.is_dir()}
fdirs = {i.filename for i in full.infolist() if i.is_dir()}


def base_name(n):
    """Strip ' copy N' from folder names and the __MACOSX prefix / '._' marker."""
    mac = n.startswith("__MACOSX/")
    if mac:
        n = n[len("__MACOSX/"):]
        parts = n.split("/")
        if parts[-1].startswith("._"):
            parts[-1] = parts[-1][2:]
        n = "/".join(parts)
    return mac, re.sub(r" copy \d+(?=/|$)", "", n)


kinds = collections.Counter()
unmatched = collections.Counter()
xattrs = collections.Counter()
mac_sizes = collections.Counter()
for i in stress.infolist():
    mac, b = base_name(i.filename)
    if mac:
        if i.is_dir():
            kinds["mac dir"] += 1
            continue
        d = stress.read(i)
        mac_sizes[len(d)] += 1
        # AppleDouble: magic 0x00051607; entries; the attributes live in the Finder-info entry's extended part
        if d[:4] == b"\x00\x05\x16\x07":
            for m in re.finditer(rb"(com\.apple\.[\w.:-]+|kMDItem\w+)", d):
                xattrs[m.group(1).decode()] += 1
        kinds["mac file" + (" (matches a google-full path)" if b in fhash or b.rstrip('/') + '/' in fdirs else "")] += 1
        continue
    if i.is_dir():
        kinds["dir" + (" in google-full" if b in fdirs else " NOT in google-full")] += 1
        if b not in fdirs:
            unmatched[re.sub(r"\d+", "N", b)] += 1
        continue
    if b not in fhash:
        kinds["file NOT in google-full"] += 1
        unmatched[re.sub(r"\d+", "N", b)] += 1
        continue
    same = hashlib.sha256(stress.read(i)).hexdigest() == fhash[b]
    kinds["file, byte-identical to google-full" if same else "file, DIFFERENT from google-full"] += 1
print(dict(kinds))
print("unmatched (digits masked):", unmatched.most_common(10))
print("AppleDouble sizes:", mac_sizes.most_common(5))
print("xattr names:", dict(xattrs))
copies = {re.search(r" copy (\d+)", i.filename).group(1) for i in stress.infolist() if " copy " in i.filename}
print("copy numbers:", len(copies), "min", min(map(int, copies)), "max", max(map(int, copies)))
