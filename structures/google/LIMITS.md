# google: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 1, export dates 2024-09-03; languages nl
- File patterns seen: 13 (csv 2, html 1, json 10)
- No media files (photos, videos, audio) in any package yet.
- Lists that were empty in every package, so their items are unknown: 0

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- Nothing.

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 2
- `search-history.json`
- `watch-history.json`

<!-- known gaps by hand: start -->
- Only a Dutch Takeout has been seen, with YouTube history as JSON and subscriptions and comments as CSV. English file names (`watch-history.json`, `search-history.json`) and HTML history files are not covered.
<!-- known gaps by hand: end -->

## Last change

- 2024-09-03: package of 2024-09-03 (nl) added: 13 new, 0 changed shape, 0 not seen since an earlier package
