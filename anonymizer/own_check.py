"""Search the copy for the account's own identifiers: the username and name given on the command line, and every
email address and phone number in the original's own profile files. Counts only.
    python3 own_check.py <original.zip> <copy.zip> <username> <full name>"""
import re, sys, zipfile
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import verify2_core as vc  # noqa: E402
orig, copy = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
user, name = sys.argv[3].casefold(), sys.argv[4].casefold()
OWN = ("personal_information.json", "profile_changes.json", "checkout_payment_information.json", "autofill_information.json",
       "signup_details.json", "instagram_profile_information.json", "account_information.json", "profile_activity.json")
emails, phones = set(), set()
for f, field, v in vc.leaves(orig):
    if f.endswith(OWN):
        emails |= {e.casefold() for e in re.findall(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", v)}
        if re.fullmatch(r"\+?[\d\s\-()]{8,}", v) and sum(c.isdigit() for c in v) >= 8:
            phones.add(re.sub(r"\D", "", v))
parts = [i.filename for i in copy.infolist()]
for i in copy.infolist():
    d = copy.read(i)
    if i.filename.endswith(".json"):
        parts.append(d.decode())
    elif i.filename.endswith((".srt", ".txt", ".html", ".csv")):
        parts.append(d.decode("utf-8", "replace"))
leaf_text = "\n".join(v for _, _, v in vc.leaves(copy))
corpus = ("\n".join(parts) + "\n" + leaf_text).casefold()
digits = re.sub(r"\D", "", corpus)
nospace = re.sub(r"[\s._\-]", "", corpus)
words = set(re.findall(r"[^\W\d_]+", corpus))
first, *rest = name.split()
print("username: in copy", user in corpus, "| without separators", user.replace("_", "").replace(".", "") in nospace)
print("full name: in copy", name in corpus, "| joined", name.replace(" ", "") in nospace)
print("first name as a word:", first in words, "| surname as a word:", rest[-1] in words if rest else None,
      "| surname without spaces:", "".join(rest) in nospace if rest else None)
print("own emails:", len(emails), "found", sum(e in corpus for e in emails),
      "| local parts (5+ chars) found", sum(e.split("@")[0] in corpus for e in emails if len(e.split("@")[0]) >= 5))
print("own phone numbers:", len(phones), "found as digit runs", sum(p in digits for p in phones))
