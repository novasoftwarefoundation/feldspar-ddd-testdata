"""Reproduces the Instagram anonymizer bugs fixed together with Dutch-export support. Builds a tiny synthetic export,
anonymizes it with a fixed key and checks the copy. Exit 0 = pass.

    python3 test_instagram.py

1. Synced contacts' first and last names were not known as names, so the fake-name pool could hand a contact
   their own name back, and a fake equal to its own original was accepted.
2. Captions in past_instagram_insights were kept, because every insights field was kept.
3. A fake-name pool word could contain an original surname of 6+ letters (Kuipers for Kuiper).
4. Subtitle files (.srt) stopped the anonymizer with an error.
5. Dutch exports: Gebruikersnaam was replaced as free text instead of as a username, and the Dutch yes/no
   values ("Waar", "Niet waar") were replaced as text.
6. When the contacts hold every name of the fake first-name pool, the emptied pool stopped the anonymizer
   (case 1 builds exactly that).
"""
import json
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import anonymize as an  # noqa: E402
import metajson  # noqa: E402

an.KEY = b"\x07" * 32       # fixed key: the same fakes on every run

contacts = [{"title": "", "media_map_data": {}, "string_map_data": {
    "First Name": {"href": "", "value": first, "timestamp": 0},
    "Last Name": {"href": "", "value": "Kuiper", "timestamp": 0},
    "Contact Information": {"href": "", "value": "", "timestamp": 0}}} for first in an.FIRST]
files = {
    "connections/contacts/synced_contacts.json": {"contacts_contact_info": contacts},
    "logged_information/past_instagram_insights/reels.json": {"organic_insights_reels": [{"string_map_data": {
        "Caption": {"href": "", "value": "Sunset over the dunes with Femke", "timestamp": 0},
        "Bijschrift": {"href": "", "value": "Zonsondergang bij de duinen", "timestamp": 0},
        "Views": {"href": "", "value": "12", "timestamp": 0}}}]},
    "your_instagram_activity/likes/liked_posts.json": [{"timestamp": 0, "media": [], "label_values": [
        {"title": "Eigenaar", "dict": [{"dict": [
            {"label": "Gebruikersnaam", "value": "zonnige.dagen_42"},
            {"label": "Naam", "value": "Zonnige Dagen"}], "title": ""}]},
        {"label": "Is een advertentie", "value": "Niet waar"},
        {"label": "Gepubliceerd", "value": "Waar"}]}],
}
srt = "1\n00:00:00,000 --> 00:00:01,500\nKijk eens naar dit uitzicht\n\n"

with tempfile.TemporaryDirectory() as d:
    src, dst = os.path.join(d, "in.zip"), os.path.join(d, "out.zip")
    with zipfile.ZipFile(src, "w") as z:
        for name, data in files.items():
            z.writestr(name, metajson.dumps(data))
        z.writestr("media/reels/202501/1234567890123456789.srt", srt)
    failed = []
    try:
        with open(os.devnull, "w") as null:
            out, sys.stdout = sys.stdout, null
            try:
                an.main(src, dst)
            finally:
                sys.stdout = out
    except Exception as e:  # noqa: BLE001
        print("FAIL anonymizer stopped:", type(e).__name__)
        sys.exit(1)
    with zipfile.ZipFile(dst) as z:
        names = z.namelist()
        get = {n.split("/")[-1]: z.read(n) for n in names}
    c = json.loads(get["synced_contacts.json"])["contacts_contact_info"]
    firsts = [x["string_map_data"]["First Name"]["value"] for x in c]
    lasts = [x["string_map_data"]["Last Name"]["value"] for x in c]
    if any(a == b for a, b in zip(an.FIRST, firsts)):
        failed.append("1: a contact's first name came out unchanged")
    if any("kuiper" in x.casefold() for x in firsts + lasts + an.LAST):
        failed.append("3: a fake-name pool word contains the original surname")
    smd = json.loads(get["reels.json"])["organic_insights_reels"][0]["string_map_data"]
    if smd["Caption"]["value"].startswith("Sunset") or smd["Bijschrift"]["value"].startswith("Zonsondergang"):
        failed.append("2: an insights caption was kept")
    if smd["Views"]["value"] != "12":
        failed.append("2: an insights count was changed")
    srt_name = [n for n in names if n.endswith(".srt")]
    if not srt_name:
        failed.append("4: the subtitle file is missing")
    else:
        lines = get[srt_name[0].split("/")[-1]].decode().split("\n")
        if lines[:2] != srt.split("\n")[:2] or lines[2] == srt.split("\n")[2] or len(lines) != len(srt.split("\n")):
            failed.append("4: subtitle timing changed or caption kept")
    lv = json.loads(get["liked_posts.json"])[0]["label_values"]
    user = lv[0]["dict"][0]["dict"][0]["value"]
    if user != an.fake_username("zonnige.dagen_42"):
        failed.append("5: Gebruikersnaam not replaced as a username")
    if lv[0]["title"] != "Eigenaar" or lv[1]["value"] != "Niet waar" or lv[2]["value"] != "Waar":
        failed.append("5: a Dutch heading or yes/no value was changed")
for f in failed:
    print("FAIL", f)
print("ok" if not failed else f"{len(failed)} failed")
sys.exit(1 if failed else 0)
