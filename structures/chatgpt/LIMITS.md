# chatgpt: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 1, export dates 2026-09-28; languages und
- File patterns seen: 9 (html 1, json 7, media 1)
- Lists that were empty in every package, so their items are unknown: 1
  - `conversations.json [].mapping.<uuid>.message.content.thoughts[].chunks`

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- Nothing.

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 3
- `conversations-000.json`
- `message_feedback.json`
- `model_comparisons.json`

<!-- known gaps by hand: start -->
- ChatGPT exports carry no field labels, so the language is recorded as `und` (undetermined).
- Large exports split `conversations.json` into `conversations-000.json`, `conversations-001.json` … listed in `export_manifest.json`; no package with that split has been added yet (generators/chatgpt/generate_chatgpt_export.py writes that shape).
<!-- known gaps by hand: end -->

## Last change

- 2026-09-28: package of 2026-09-28 (und) added: 9 new, 0 changed shape, 0 not seen since an earlier package
