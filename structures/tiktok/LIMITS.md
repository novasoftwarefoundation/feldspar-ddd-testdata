# tiktok: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 2, export dates 2024-09-02, 2024-12-10; languages en
- File patterns seen: 2 (json 2)
- No media files (photos, videos, audio) in any package yet.
- Lists that were empty in every package, so their items are unknown: 2
  - `user_data.json .Tiktok Live.Go Live Settings.SettingsMap.Hide comments that contain the following keywords from your LIVE`
  - `user_data.json .Tiktok Live.Go Live Settings.SettingsMap.People you assigned to moderate your LIVE`

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- 3 × key part replaced by <value>: user_data.json $.Direct Messages.Chat History.ChatHistory
- 1 × key that is user data replaced by <name>: user_data.json $.App Settings.Settings.SettingsMap.Family Content Preferences

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 0

Files that newer packages no longer have:
- `user_data_tiktok.json (not seen since 2024-09-02)`

<!-- known gaps by hand: start -->
- The 2024-12 package had no dates in its zip; its date is the day it was stored, not the export date.
- The two packages use different file names (`user_data_tiktok.json` and `user_data.json`), so their JSON is described by two schemas. Because the 2024-12 date is uncertain, the order of that rename is too.
- Direct message keys are written as `Chat History with <value>:`; the participant names are left out.
<!-- known gaps by hand: end -->

## Last change

- 2024-12-10: package of 2024-12-10 (en) added: 1 new, 0 changed shape, 1 not seen since an earlier package
