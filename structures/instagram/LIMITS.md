# instagram: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 1, export dates 2024-03-04; languages de
- File patterns seen: 71 (json 48, media 7, text 16)
- Lists that were empty in every package, so their items are unknown: 7
  - `connections/followers_and_following/close_friends.json .relationships_close_friends[].media_list_data`
  - `connections/followers_and_following/followers_<n>.json [].media_list_data`
  - `connections/followers_and_following/following.json .relationships_following[].media_list_data`
  - `connections/followers_and_following/recently_unfollowed_accounts.json .relationships_unfollowed_users[].media_list_data`
  - `connections/followers_and_following/removed_suggestions.json .relationships_dismissed_suggested_users[].media_list_data`
  - `your_instagram_activity/messages/inbox/<name>_<id>/message_<n>.json .magic_words`
  - `your_instagram_activity/messages/secret_conversations.json .ig_secret_conversations.calls`

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- 6 × name part replaced by <value>: your_activity_across_facebook/messages/inbox/…
- 16 × name part replaced by <value>: your_instagram_activity/messages/inbox/…

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 12
- `account_privacy_changes.json`
- `ads_clicked.json`
- `ads_interests.json`
- `followers.json`
- `pending_follow_requests.json`
- `post_comments.json`
- `profile_changes.json`
- `profile_searches.json`
- `recent_follow_requests.json`
- `reels.json`
- `subscription_for_no_ads.json`
- `threads_viewed.json`

<!-- known gaps by hand: start -->

<!-- known gaps by hand: end -->

## Last change

- 2024-03-04: package of 2024-03-04 (de) added: 71 new, 0 changed shape, 0 not seen since an earlier package
