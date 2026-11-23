#!/usr/bin/env python3
"""Synthetic Instagram / Facebook data download packages (DDPs) for load tests.

Fully synthetic content: accounts are "konto_00042", people are "Testperson 42",
the participant is "Pat Beispiel".

    python3 generators/meta/gen_ddp.py --platform instagram --profile heavy --lang de --format new -o out.zip
    python3 generators/meta/gen_ddp.py --platform facebook --profile extreme --media-mb 2000 -o out.zip

Profiles (record counts per file) are documented in PROFILES below. --format new writes Meta's current ``label_values`` shapes,
--format old the older ``string_map_data`` / ``*_v2`` shapes. --lang picks the
field labels (de, en, nl; labels are taken from the scripts' own label lists).
--media-mb adds stored (uncompressed) dummy media files to reach a realistic
zip size for exports that include photos and videos.
"""
import argparse
import json
import random
import zipfile

T_END = 1763856000  # 2025-11-23, end of the synthetic timeline
DAY = 86400

# Record counts. "days" is the length of the account history.
# Sources / assumptions:
#  - viewed posts / videos / ads: Meta keeps only ~6-13 days in the export
#  - link history: 30 days; following: capped at 7,500 (Instagram); friends: 5,000 (Facebook)
#  - everything else: all-time, rate x history length
PROFILES = {
    "typical": dict(days=365, viewed=2000, videos=1000, ads=500, likes=2000, liked_comments=200,
                    comments=200, saved=100, searches=300, following=400, followers=400, story=500,
                    links=300, offmeta=2000, logins=200, topics=100, advertisers=200, friends=300, feed=3000),
    "heavy": dict(days=5 * 365, viewed=15000, videos=15000, ads=5000, likes=40000, liked_comments=4000,
                  comments=3000, saved=2000, searches=3000, following=3000, followers=5000, story=10000,
                  links=3000, offmeta=30000, logins=2000, topics=500, advertisers=1500, friends=1500, feed=20000),
    "extreme": dict(days=10 * 365, viewed=60000, videos=60000, ads=30000, likes=300000, liked_comments=30000,
                    comments=30000, saved=20000, searches=20000, following=7500, followers=100000, story=50000,
                    links=10000, offmeta=200000, logins=10000, topics=1000, advertisers=5000, friends=5000,
                    feed=100000),
}

LABELS = {
    "de": dict(owner="Eigentümer", username="Benutzername", name="Name", url="URL", time="Zeit",
               comment="Kommentar", media_owner="Medieninhaber", search="Suche", caption="Bildunterschrift",
               reaction="Reaktion", title="Titel", saved_on="Gespeichert am", author="Autor",
               possessive=lambda o, n: f"{o}s {n}", post="Beitrag", video="Video", like="Gefällt mir",
               actor_likes=lambda a, o: f"{a} gefällt {o}s Beitrag.", actor_saved=lambda a, o: f"{a} hat {o}s Beitrag gespeichert.",
               actor_commented=lambda a, o: f"{a} hat {o}s Beitrag kommentiert."),
    "en": dict(owner="Owner", username="Username", name="Name", url="URL", time="Time",
               comment="Comment", media_owner="Media Owner", search="Search", caption="Caption",
               reaction="Reaction", title="Title", saved_on="Saved on", author="Author",
               possessive=lambda o, n: f"{o}'s {n}", post="post", video="video", like="Like",
               actor_likes=lambda a, o: f"{a} likes {o}'s post.", actor_saved=lambda a, o: f"{a} saved {o}'s post.",
               actor_commented=lambda a, o: f"{a} commented on {o}'s post."),
    "nl": dict(owner="Eigenaar", username="Gebruikersnaam", name="Naam", url="URL", time="Tijd",
               comment="Opmerking", media_owner="Media-eigenaar", search="Zoeken", caption="Bijschrift",
               reaction="Reactie", title="Titel", saved_on="Opgeslagen op", author="Auteur",
               possessive=lambda o, n: f"{n} van {o}", post="Bericht", video="Video", like="Vind ik leuk",
               actor_likes=lambda a, o: f"{a} vindt het bericht van {o} leuk.", actor_saved=lambda a, o: f"{a} heeft het bericht van {o} opgeslagen.",
               actor_commented=lambda a, o: f"{a} heeft gereageerd op het bericht van {o}."),
}

ME = "Pat Beispiel"
WORDS = ("Sonne Urlaub Kaffee Training Rezept Konzert Bahn Hund Katze Berlin Hamburg Strand Buch "
         "Projekt Abend Wochenende Freunde Musik Film Serie Garten Fahrrad Laufen Kochen").split()


class Gen:
    def __init__(self, seed: int, prof: dict, lang: str):
        self.r = random.Random(seed)
        self.p = prof
        self.L = LABELS[lang]

    def ts(self, window_days=None):
        days = window_days or self.p["days"]
        return T_END - self.r.randrange(days * DAY)

    def acct(self, n=5000):
        return f"konto_{self.r.randrange(n):05d}"

    def person(self, n=5000):
        return f"Testperson {self.r.randrange(n)}"

    def text(self, lo=3, hi=25):
        return " ".join(self.r.choice(WORDS) for _ in range(self.r.randint(lo, hi)))

    def code(self):
        return "".join(self.r.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz0123456789_-") for _ in range(11))

    # ---------------- Instagram -----------------
    def ig_owner_block(self, user):
        L = self.L
        return {"dict": [{"dict": [
            {"label": L["url"], "value": f"https://www.instagram.com/{user}"},
            {"label": L["name"], "value": user.replace("konto_", "Konto ")},
            {"label": L["username"], "value": user}], "title": ""}], "title": L["owner"]}

    def ig_content(self, n, window, fmt, root_key, with_caption=True):
        L = self.L
        out = []
        for _ in range(n):
            user, t, url = self.acct(), self.ts(window), f"https://www.instagram.com/p/{self.code()}/"
            if fmt == "new":
                lv = [{"label": L["url"], "value": url, "href": url}, self.ig_owner_block(user)]
                if with_caption and self.r.random() < 0.6:
                    lv.insert(0, {"label": L["caption"], "value": self.text()})
                out.append({"timestamp": t, "media": [], "label_values": lv, "fbid": str(self.r.randrange(10**15))})
            else:
                out.append({"string_map_data": {L["author"]: {"value": user}, L["time"]: {"timestamp": t}}})
        return out if fmt == "new" else {root_key: out}

    def instagram(self, fmt):
        p, L = self.p, self.L
        A = "your_instagram_activity/"
        files = {
            "ads_information/ads_and_topics/posts_viewed.json": self.ig_content(p["viewed"], 13, fmt, "impressions_history_posts_seen"),
            "ads_information/ads_and_topics/videos_watched.json": self.ig_content(p["videos"], 13, fmt, "impressions_history_videos_watched"),
            "ads_information/ads_and_topics/ads_viewed.json": self.ig_content(p["ads"], 13, fmt, "impressions_history_ads_seen"),
            A + "story_interactions/stories_viewed.json": self.ig_content(p["story"] // 2, 13, fmt, "impressions_history_stories_seen", False),
        }
        if fmt == "new":
            files[A + "likes/liked_posts.json"] = self.ig_content(p["likes"], None, "new", "", False)
        else:
            files[A + "likes/liked_posts.json"] = {"likes_media_likes": [
                {"title": self.acct(), "string_list_data": [{"href": f"https://www.instagram.com/p/{self.code()}/", "value": "\U0001f44d", "timestamp": self.ts()}]}
                for _ in range(p["likes"])]}
        files[A + "likes/liked_comments.json"] = {"likes_comment_likes": [
            {"title": self.acct(), "string_list_data": [{"href": f"https://www.instagram.com/p/{self.code()}/c/{self.r.randrange(10**17)}", "value": "\U0001f44d", "timestamp": self.ts()}]}
            for _ in range(p["liked_comments"])]}
        for stem, key in (("story_likes", "story_activities_story_likes"), ("polls", "story_activities_polls"), ("emoji_sliders", "story_activities_emoji_sliders")):
            files[A + f"story_interactions/{stem}.json"] = {key: [
                {"title": self.acct(), "string_list_data": [{"timestamp": self.ts()}]} for _ in range(p["story"] // 6)]}
        files[A + "saved/saved_posts.json"] = {"saved_saved_media": [
            {"title": self.acct(), "string_map_data": {L["saved_on"]: {"href": f"https://www.instagram.com/p/{self.code()}/", "timestamp": self.ts()}}}
            for _ in range(p["saved"])]}
        comments = [{"media": [], "string_map_data": {L["comment"]: {"value": self.text(1, 12)}, L["media_owner"]: {"value": self.acct()}, L["time"]: {"timestamp": self.ts()}}}
                    for _ in range(p["comments"])]
        files[A + "comments/post_comments_1.json"] = comments[: len(comments) * 4 // 5]
        files[A + "comments/reels_comments.json"] = {"comments_reels_comments": comments[len(comments) * 4 // 5:]}
        files["logged_information/recent_searches/word_or_phrase_searches.json"] = {"searches_keyword": [
            {"title": "", "string_map_data": {L["search"]: {"value": self.text(1, 3)}, L["time"]: {"timestamp": self.ts()}}} for _ in range(p["searches"] // 2)]}
        files["logged_information/recent_searches/profile_searches.json"] = {"searches_user": [
            {"title": "", "string_list_data": [{"href": f"https://www.instagram.com/{u}", "value": u, "timestamp": self.ts()}]}
            for u in (self.acct() for _ in range(p["searches"] // 2))]}
        files["connections/followers_and_following/following.json"] = {"relationships_following": [
            {"title": u, "string_list_data": [{"href": f"https://www.instagram.com/_u/{u}", "timestamp": self.ts()}]}
            for u in (f"konto_{i:06d}" for i in range(p["following"]))]}
        followers = [{"title": "", "media_list_data": [], "string_list_data": [{"href": f"https://www.instagram.com/{u}", "value": u, "timestamp": self.ts()}]}
                     for u in (f"folger_{i:06d}" for i in range(p["followers"]))]
        for part in range(0, max(1, len(followers)), 10000):  # Meta splits followers into numbered files
            files[f"connections/followers_and_following/followers_{part // 10000 + 1}.json"] = followers[part: part + 10000]
        files["connections/followers_and_following/following_hashtags.json"] = {"relationships_following_hashtags": [
            {"title": w, "string_list_data": [{"href": f"https://www.instagram.com/explore/tags/{w.lower()}", "value": w, "timestamp": self.ts()}]} for w in WORDS]}
        files["preferences/your_topics/your_topics.json"] = {"topics_your_topics": [
            {"string_map_data": {L["name"]: {"value": f"Thema {i}"}}} for i in range(p["topics"])]}
        files["logged_information/link_history/link_history.json"] = [
            {"timestamp": self.ts(30), "label_values": [{"label": L["url"], "value": f"https://www.beispiel-{self.r.randrange(500)}.de/artikel/{self.r.randrange(10**6)}"}]}
            for _ in range(p["links"])]
        files["apps_and_websites_off_of_instagram/apps_and_websites/your_activity_off_meta_technologies.json"] = self.offmeta(fmt)
        files["ads_information/instagram_ads_and_businesses/advertisers_using_your_activity_or_information.json"] = {
            "label_values": [{"label": "Werbetreibende", "vec": [{"value": f"Firma {i} GmbH"} for i in range(p["advertisers"])]}]}
        files["ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json"] = {
            "label_values": [{"label": "Kategorien", "vec": [{"value": f"Kategorie {i}"} for i in range(50)]}]}
        for stem, key in (("login_activity", "account_history_login_history"), ("logout_activity", "account_history_logout_history")):
            files[f"security_and_login_information/login_and_profile_creation/{stem}.json"] = {key: [
                {"title": "2025", "string_map_data": {"IP Address": {"value": "192.0.2.1"}, L["time"]: {"timestamp": self.ts()}}} for _ in range(p["logins"] // 2)]}
        files["personal_information/personal_information/personal_information.json"] = {"profile_user": [{"string_map_data": {L["username"]: {"value": "pat.beispiel"}}}]}
        return files

    def offmeta(self, fmt):
        p = self.p
        sites = [f"shop-{i}.example" for i in range(max(5, p["offmeta"] // 200))]
        events = ["PAGE_VIEW", "VIEW_CONTENT", "SEARCH", "ADD_TO_CART", "PURCHASE", "CUSTOM", "AD_IMPRESSION"]
        per = {s: [] for s in sites}
        for _ in range(p["offmeta"]):
            per[self.r.choice(sites)].append((self.r.choice(events), self.ts(180)))
        if fmt == "new":
            return [{"title": s, "label_values": [{"label": "Ereignisse", "vec": [
                {"dict": [{"label": "ID", "value": str(self.r.randrange(10**15))}, {"label": "Ereignis", "value": e}, {"label": "Zeit", "timestamp_value": t}]}
                for e, t in evs]}]} for s, evs in per.items()]
        return {"off_facebook_activity_v2": [{"name": s, "events": [{"id": 1, "type": e, "timestamp": t} for e, t in evs]} for s, evs in per.items()]}

    # ---------------- Facebook -----------------
    def facebook(self, fmt):
        p, L = self.p, self.L
        A = "your_facebook_activity/"
        feed = {"label_values": [{"label": "Inhalte", "vec": [
            {"dict": [{"label": "", "value": f"{L['possessive'](self.person(), L['post'])}: {self.text()}"},
                      {"label": "URL", "href": u, "value": u}, {"label": "Zeit", "timestamp_value": self.ts(13)}]}
            for u in (f"https://www.facebook.com/testperson.{self.r.randrange(5000)}/posts/pfbid0{self.code()}" for _ in range(p["feed"]))]}]}
        files = {"logged_information/interactions/content_that_has_been_shown_to_you_in_your_feed.json": feed}
        files["ads_information/ads_viewed.json"] = [
            {"timestamp": self.ts(13), "label_values": [{"label": "Titel", "value": f"Firma {self.r.randrange(2000)} GmbH"},
                                                         {"label": "URL", "value": f"https://www.facebook.com/ads/library/?id={self.r.randrange(10**15)}"}]}
            for _ in range(p["ads"])]
        files["ads_information/story_views_in_past_7_days.json"] = {"label_values": [{"label": "Anzahl", "value": str(p["story"] // 50)}]}
        likes = []
        for _ in range(p["likes"]):
            owner, t = self.person(), self.ts()
            url = f"https://www.facebook.com/testperson.{self.r.randrange(5000)}/posts/pfbid0{self.code()}"
            if fmt == "new":
                likes.append({"timestamp": t, "label_values": [
                    {"label": L["reaction"], "value": L["like"]}, {"label": L["url"], "value": url, "href": url},
                    {"title": L["owner"], "dict": [{"dict": [{"label": L["name"], "value": owner}, {"label": L["url"], "value": "https://www.facebook.com/x"}], "title": ""}]},
                    {"label": L["title"], "value": L["possessive"](owner, L["post"])}]})
            else:
                likes.append({"timestamp": t, "data": [{"reaction": {"reaction": "LIKE", "actor": ME}}], "title": L["actor_likes"](ME, owner)})
        for part in range(0, max(1, len(likes)), 50000):
            files[A + f"comments_and_reactions/likes_and_reactions_{part // 50000 + 1}.json"] = likes[part: part + 50000]
        files[A + "stories/story_reactions.json"] = [
            {"timestamp": self.ts(), "label_values": [{"label": L["reaction"], "value": "❤️"}, self.fb_owner()]} for _ in range(p["story"])]
        files[A + "saved_items_and_collections/your_saved_items.json"] = {"saves_v2": [
            {"timestamp": self.ts(), "title": L["actor_saved"](ME, self.person())} for _ in range(p["saved"])]}
        files[A + "comments_and_reactions/comments.json"] = {"comments_v2": [
            {"timestamp": self.ts(), "title": L["actor_commented"](ME, self.person()), "data": [{"comment": {"timestamp": self.ts(), "comment": self.text(1, 15), "author": ME}}]}
            for _ in range(p["comments"])]}
        files["logged_information/search/your_search_history.json"] = {"searches_v2": [
            {"timestamp": self.ts(), "data": [{"text": f"\"{self.text(1, 3)}\""}], "title": f"{ME} hat auf Facebook gesucht"} for _ in range(p["searches"])]}
        files["connections/friends/your_friends.json"] = {"friends_v2": [{"name": f"Testperson {i}", "timestamp": self.ts()} for i in range(p["friends"])]}
        files["connections/followers/who_you've_followed.json"] = {"following_v3": [{"name": f"Seite {i}", "timestamp": self.ts()} for i in range(p["following"])]}
        files[A + "pages/pages_and_profiles_you_follow.json"] = {"pages_followed_v2": [{"title": f"Seite {i}", "timestamp": self.ts()} for i in range(p["following"] // 5)]}
        files[A + "pages/pages_you've_liked.json"] = {"page_likes_v2": [{"name": f"Seite {i}", "timestamp": self.ts()} for i in range(p["following"] // 5)]}
        files["logged_information/other_logged_information/ads_interests.json"] = {"topics_v2": [f"Thema {i}" for i in range(p["topics"])]}
        files[A + "other_activity/link_history.json"] = [
            {"timestamp": self.ts(30), "label_values": [{"label": "URL", "value": f"https://www.beispiel-{self.r.randrange(500)}.de/artikel/{self.r.randrange(10**6)}"}]}
            for _ in range(p["links"])]
        files["apps_and_websites_off_of_facebook/your_activity_off_meta_technologies.json"] = self.offmeta(fmt)
        files["ads_information/advertisers_using_your_activity_or_information.json"] = {
            "label_values": [{"label": "Werbetreibende", "vec": [{"value": f"Firma {i} GmbH"} for i in range(p["advertisers"])]}]}
        files["ads_information/advertisers_you've_interacted_with.json"] = [
            {"timestamp": self.ts(), "label_values": [{"label": "Aktion", "value": "Werbeanzeige angeklickt"}, {"label": "Titel", "value": f"Firma {self.r.randrange(2000)} GmbH"}]}
            for _ in range(p["advertisers"])]
        files["ads_information/other_categories_used_to_reach_you.json"] = {"label_values": [{"label": "Kategorien", "vec": [{"value": f"Kategorie {i}"} for i in range(50)]}]}
        files["ads_information/ad_preferences.json"] = {"label_values": [{"label": "Werbethemen", "vec": [{"value": f"Thema {i}"} for i in range(p["topics"])]}]}
        files["security_and_login_information/logins_and_logouts.json"] = {"account_accesses_v2": [
            {"action": self.r.choice(["Login", "Log out"]), "timestamp": self.ts(), "site": "www.facebook.com", "ip_address": "192.0.2.1"} for _ in range(p["logins"])]}
        files["profile_information/profile_information.json"] = {"profile_v2": {"name": {"full_name": ME}, "registration_timestamp": T_END - p["days"] * DAY}}
        files[A + "posts/your_posts__check_ins__photos_and_videos_1.json"] = [{"timestamp": self.ts(), "data": [{"post": self.text()}]} for _ in range(max(10, p["comments"] // 10))]
        return files

    def fb_owner(self):
        L = self.L
        return {"title": L["owner"], "dict": [{"dict": [{"label": L["name"], "value": self.person()}], "title": ""}]}


def meta_text(s: str) -> str:
    """Meta writes non-ASCII text as latin-1 escaped UTF-8 bytes ("Ã¼" for "ü")."""
    return s.encode("utf-8").decode("latin-1")


def mojibake(node):
    if isinstance(node, str):
        return meta_text(node)
    if isinstance(node, list):
        return [mojibake(x) for x in node]
    if isinstance(node, dict):
        return {meta_text(k): mojibake(v) for k, v in node.items()}
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["instagram", "facebook"], required=True)
    ap.add_argument("--profile", choices=list(PROFILES), required=True)
    ap.add_argument("--scale", type=float, default=1.0, help="multiply all record counts (stress tests)")
    ap.add_argument("--lang", choices=list(LABELS), default="de")
    ap.add_argument("--format", choices=["new", "old"], default="new")
    ap.add_argument("--media-mb", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    prof = {k: (v if k == "days" else int(v * a.scale)) for k, v in PROFILES[a.profile].items()}
    g = Gen(a.seed, prof, a.lang)
    files = g.instagram(a.format) if a.platform == "instagram" else g.facebook(a.format)
    json_bytes = 0
    with zipfile.ZipFile(a.output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, data in files.items():
            raw = json.dumps(mojibake(data), indent=2, ensure_ascii=True).encode()  # Meta pretty-prints JSON
            json_bytes += len(raw)
            zf.writestr(path, raw)
        remaining = a.media_mb * 1024 * 1024
        block = random.Random(a.seed).randbytes(1024 * 1024)  # incompressible, like real JPEG/MP4
        i = 0
        while remaining > 0:
            size = min(remaining, 200 * 1024 * 1024)
            with zf.open(f"media/posts/202{i % 6}01/video_{i:04d}.mp4", "w", force_zip64=True) as f:
                for _ in range(size // len(block)):
                    f.write(block)
            remaining -= size
            i += 1
    print(json.dumps({"output": a.output, "files": len(files), "json_mb": round(json_bytes / 2**20, 1),
                      "records": {k: v for k, v in prof.items() if k != "days"}}))


if __name__ == "__main__":
    main()
