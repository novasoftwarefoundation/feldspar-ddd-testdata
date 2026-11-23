# feldspar-ddd-testdata

Test data tools for digital data donation (DDD): the structure rules of the data download packages that platforms
such as Instagram, Facebook, Google, TikTok and ChatGPT give their users, and scripts that build synthetic packages
from those rules. A JavaScript sibling, `feldspar-ddd-js`, will follow next to this repository.

**This repository never holds a package.** It holds no zips, no exports and no value from one: no names, usernames,
emails, ids or text. It keeps only the structure: which files a package has, which keys their JSON has, the types of
the values and the platform's own field labels (such as "Owner" or "Eigentümer"). Share only synthetic or anonymized
packages as test data; a package with personal data may be read locally with `ddd.py add`, and is never stored here.

Everything runs with Python 3.9 or newer and nothing else.

## The structures

Each platform has a folder in [`structures/`](structures):

- `files.yaml`: every file pattern seen in any package (for example
  `your_instagram_activity/messages/inbox/<name>_<id>/message_<n>.json`), with the number of packages it was seen in,
  the first and last export date, and the JSON Schema that describes it.
- `schemas/`: one [JSON Schema](https://json-schema.org/draft/2020-12) per JSON file pattern, with keys, nesting,
  types, optional and required keys, and the platform's labels as `enum`. Bookkeeping is kept in `x-` keywords, which
  standard JSON Schema tools ignore: `x-seen-in`, `x-first-seen`, `x-last-seen`, `x-langs`, `x-not-seen-since`
  and `x-changes`.
- `LIMITS.md`: what the structure does not cover yet.

A structure is only as complete as the packages it came from. A file, key or label that no package has shown yet is
not in it, and a list that was empty in every package has no known items. Read the limits before trusting a gap:
[Instagram](structures/instagram/LIMITS.md), [Facebook](structures/facebook/LIMITS.md),
[Google](structures/google/LIMITS.md), [TikTok](structures/tiktok/LIMITS.md),
[ChatGPT](structures/chatgpt/LIMITS.md).

Each platform has one combined structure that grows with every package. Adding a package adds what is new, records
a changed shape as a change (old and new shape, with the date) instead of overwriting it, and marks a part that a
newer package in the same language no longer has as "not seen since" instead of deleting it. Git history keeps every
version.

## Commands

Add a package to its platform's structure (the export date is read from the zip, or pass `--date`):

    python3 ddd.py add instagram-export.zip --platform instagram --lang en

Compare two packages, snapshot files or structure folders, for example a new package against what is known:

    python3 ddd.py diff structures/instagram instagram-export.zip --platform instagram

List what a package has that the structure doesn't know yet (exit code 1 when there is something):

    python3 ddd.py check instagram-export.zip --platform instagram

Write one package's structure to a file, to review it before adding:

    python3 ddd.py extract instagram-export.zip --platform instagram -o instagram-snapshot.json

Every name that can hold personal data becomes a placeholder: `<name>_<id>` for message folders, `<id>` for media
files, `<value>` for a word that is also a value in the package, `<text>` for long free text. Whatever the extractor
is unsure about is left out and counted, by place only, in `LIMITS.md`. Words that are the platform's own but also
occur as values (Google's product names, for example) can be listed under `wording` in `files.yaml`.

## Generators

Build a synthetic package from a platform's combined structure. The same structure, options and seed give the same
zip, byte for byte:

    python3 ddd.py generate --platform instagram --lang en -o instagram-synthetic.zip

Options: `--records` (most items per list, default 5), `--seed`, `--date` (export date) and `--include-old` (also
parts marked "not seen since").

Build a large synthetic Instagram or Facebook package for load tests, with fixed record counts per profile
(`typical`, `heavy`, `extreme`), `--scale` to multiply them, `--format new|old`, field labels in `--lang de|en|nl`,
and `--media-mb` to add dummy media:

    python3 generators/meta/generate_meta_export.py --platform instagram --profile typical -o instagram-typical.zip

Build a large synthetic ChatGPT export for load tests; conversations over `--part-mib` are split into
`conversations-000.json`, `conversations-001.json` … as in large exports:

    python3 generators/chatgpt/generate_chatgpt_export.py chatgpt-600mib.zip --mib 600 --months 36

## Anonymizer

Replace every personal value of an Instagram JSON export with a consistent fake one, keeping the structure exactly
(same files, keys, list lengths, types and Meta's JSON format); photos and videos become tiny placeholders:

    python3 anonymizer/instagram/anonymize.py instagram-export.zip instagram-anonymized.zip

Then compare the two and scan the copy for the original's personal values; it prints counts only:

    python3 anonymizer/instagram/verify.py instagram-export.zip instagram-anonymized.zip --username <username> --email <email>

The fake values change on every run, and the key that maps them is never stored. The placeholders in
`anonymizer/instagram/placeholders/` were made with `mkvideo.swift` (macOS).

## License

MIT, see [LICENSE](LICENSE).
