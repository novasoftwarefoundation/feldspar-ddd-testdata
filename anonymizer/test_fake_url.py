"""Reproduces the mixed-case host bug: a URL whose host is written with capitals kept its host unchanged, in the
Instagram, Google Takeout, TikTok and ChatGPT anonymizers. Exit 0 = pass.

    python3 test_fake_url.py
"""
import sys
from urllib.parse import urlsplit

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import anonymize as an  # noqa: E402

instagram_url = an.fake_url          # the other tools replace an.fake_url when imported: keep this one
import takeout  # noqa: E402
import tiktok_anon  # noqa: E402
import cg_anon  # noqa: E402

URLS = ("https://ExampleShop.com/page", "https://WWW.Example-Shop.nl/a?b=c", "http://example.org/x")
failed = 0
for tool, fake in (("anonymize", instagram_url), ("takeout", takeout.g_fake_url), ("tiktok_anon", tiktok_anon.tt_url),
                   ("cg_anon", cg_anon.cg_url)):
    for u in URLS:
        old, new = urlsplit(u), urlsplit(fake(u))
        ok = (old.hostname.split(".")[-2] not in new.hostname            # the site name is replaced
              and new.hostname.split(".")[-1] == old.hostname.split(".")[-1]   # the top-level domain is kept
              and len(new.netloc) == len(old.netloc))
        if not ok:
            failed += 1
            print("FAIL", tool, "host not replaced for a", "capitalised" if old.netloc != old.netloc.lower() else "lowercase", "host")
print("ok" if not failed else f"{failed} failed")
sys.exit(1 if failed else 0)
