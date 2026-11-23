# instagram: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 2, export dates 2024-03-04, 2026-11-23; languages de, en
- File patterns seen: 138 (json 106, media 16, text 16)
- Lists that were empty in every package, so their items are unknown: 68
  - `ads_information/ads_and_topics/ads_viewed.json [].media`
  - `ads_information/ads_and_topics/in-app_message.json .media`
  - `ads_information/ads_and_topics/posts_viewed.json [].label_values[].vec`
  - `ads_information/ads_and_topics/posts_viewed.json [].media`
  - `ads_information/ads_and_topics/posts_you're_interested_or_not_interested_in.json [].media`
  - `ads_information/ads_and_topics/posts_you're_not_interested_in.json [].media`
  - `ads_information/ads_and_topics/profiles_you're_not_interested_in.json .media`
  - `ads_information/ads_and_topics/videos_watched.json [].media`
  - `ads_information/instagram_ads_and_businesses/ad_preferences.json .label_values[].vec`
  - `ads_information/instagram_ads_and_businesses/ad_preferences.json .media`
  - `ads_information/instagram_ads_and_businesses/advertisers_using_your_activity_or_information.json .media`
  - `ads_information/instagram_ads_and_businesses/information_you've_submitted_to_advertisers.json [].media`
  - `ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json .media`
  - `connections/followers_and_following/close_friends.json .relationships_close_friends[].media_list_data`
  - `connections/followers_and_following/followers_<n>.json [].media_list_data`
  - `connections/followers_and_following/following.json .relationships_following[].media_list_data`
  - `connections/followers_and_following/pending_follow_requests.json .media`
  - `connections/followers_and_following/recently_unfollowed_accounts.json .relationships_unfollowed_users[].media_list_data`
  - `connections/followers_and_following/recently_unfollowed_profiles.json [].media`
  - `connections/followers_and_following/removed_suggestions.json .relationships_dismissed_suggested_users[].media_list_data`
  - `logged_information/link_history/link_history.json [].media`
  - `logged_information/link_history/your_link_history_settings.json .media`
  - `logged_information/past_instagram_insights/reels.json .organic_insights_reels[].media_map_data.Media Thumbnail.dubbing_info`
  - `logged_information/past_instagram_insights/reels.json .organic_insights_reels[].media_map_data.Media Thumbnail.media_variants`
  - `logged_information/past_instagram_insights/stories.json .organic_insights_stories[].media_map_data.Media Thumbnail.dubbing_info`
  - `logged_information/past_instagram_insights/stories.json .organic_insights_stories[].media_map_data.Media Thumbnail.media_variants`
  - `personal_information/autofill_information/autofill_information.json .media`
  - `personal_information/device_information/device_camera_effects_support.json [].media`
  - `personal_information/information_about_you/locations_of_interest.json .media`
  - `personal_information/information_about_you/profile_based_in.json .media`
  - `personal_information/personal_information/instagram_friend_map.json .label_values[].dict`
  - `personal_information/personal_information/instagram_friend_map.json .media`
  - `personal_information/personal_information/instagram_profile_information.json .media`
  - `personal_information/personal_information/note_and_repost_interactions.json [].media`
  - `preferences/settings/notification_preferences.json .media`
  - `preferences/your_topics/your_ads_see_more/see_less_topics.json [].label_values[].dict`
  - `preferences/your_topics/your_ads_see_more/see_less_topics.json [].media`
  - `security_and_login_information/login_and_profile_creation/profile_activity.json [].media`
  - `your_instagram_activity/likes/liked_posts.json [].media`
  - `your_instagram_activity/media/other_content.json [].label_values[].dict`
  - `your_instagram_activity/media/other_content.json [].label_values[].vec`
  - `your_instagram_activity/media/other_content.json [].media`
  - `your_instagram_activity/media/posts.json [].label_values[].dict[].dict[].dict`
  - `your_instagram_activity/media/posts.json [].label_values[].dict[].dict[].vec`
  - `your_instagram_activity/media/posts.json [].label_values[].vec`
  - `your_instagram_activity/media/posts.json [].media`
  - `your_instagram_activity/media/reels.json .ig_reels_media[].media[].dubbing_info`
  - `your_instagram_activity/media/reels.json .ig_reels_media[].media[].media_variants`
  - `your_instagram_activity/media/stories.json .ig_stories[].dubbing_info`
  - `your_instagram_activity/media/stories.json .ig_stories[].media_variants`
  - `your_instagram_activity/messages/inbox/<name>_<id>/message_<n>.json .magic_words`
  - `your_instagram_activity/messages/inbox/<name>_<id>/message_<n>.json .messages[].sticker.ai_stickers`
  - `your_instagram_activity/messages/message_requests/<name>_<id>/message_<n>.json .magic_words`
  - `your_instagram_activity/messages/secret_conversations.json .ig_secret_conversations.calls`
  - `your_instagram_activity/other_activity/your_information_download_requests.json .label_values[].vec`
  - `your_instagram_activity/other_activity/your_information_download_requests.json .media`
  - `your_instagram_activity/saved/saved_collections.json [].media`
  - `your_instagram_activity/saved/saved_posts.json [].media`
  - `your_instagram_activity/shopping/checkout_payment_information.json .media`
  - `your_instagram_activity/shopping/recently_viewed_items.json .media`
  - `your_instagram_activity/shopping/wishlist_items.json .media`
  - `your_instagram_activity/story_interactions/emoji_sliders.json .media`
  - `your_instagram_activity/story_interactions/emoji_story_reactions.json [].media`
  - `your_instagram_activity/story_interactions/polls.json [].media`
  - `your_instagram_activity/story_interactions/questions.json .media`
  - `your_instagram_activity/story_interactions/stories_viewed.json [].media`
  - `your_instagram_activity/story_interactions/story_likes.json [].media`
  - `your_instagram_activity/threads/threads_and_replies.json .text_post_app_text_posts[].media[].dubbing_info`

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- 1 × label not kept (unsure it is the platform's wording): ads_information/ads_and_topics/ads_viewed.json[].label_values[].label
- 1 × label not kept (unsure it is the platform's wording): ads_information/ads_and_topics/posts_viewed.json[].label_values[].label
- 1 × label not kept (unsure it is the platform's wording): ads_information/ads_and_topics/videos_watched.json[].label_values[].label
- 2 × label not kept (unsure it is the platform's wording): ads_information/instagram_ads_and_businesses/advertisers_using_your_activity_or_information.json.label_values[].label
- 1 × label not kept (unsure it is the platform's wording): personal_information/autofill_information/autofill_information.json.label_values[].label
- 1 × label not kept (unsure it is the platform's wording): personal_information/device_information/device_camera_effects_support.json[].label_values[].label
- 2 × label not kept (unsure it is the platform's wording): personal_information/personal_information/instagram_profile_information.json.label_values[].label
- 1 × label not kept (unsure it is the platform's wording): your_instagram_activity/media/other_content.json[].label_values[].label
- 1 × label not kept (unsure it is the platform's wording): your_instagram_activity/media/posts.json[].label_values[].dict[].dict[].label
- 1 × label not kept (unsure it is the platform's wording): your_instagram_activity/media/posts.json[].label_values[].label
- 1 × label not kept (unsure it is the platform's wording): your_instagram_activity/shopping/checkout_payment_information.json.label_values[].dict[].dict[].label
- 1 × long key replaced by <text>: logged_information/past_instagram_insights/content_interactions.json $.organic_insights_interactions[].string_map_data
- 6 × name part replaced by <value>: your_activity_across_facebook/messages/inbox/…
- 16 × name part replaced by <value>: your_instagram_activity/messages/inbox/…

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 6
- `account_privacy_changes.json`
- `ads_clicked.json`
- `ads_interests.json`
- `post_comments.json`
- `recent_follow_requests.json`
- `subscription_for_no_ads.json`

<!-- known gaps by hand: start -->
- Meta writes field labels in the participant's language. The 2024 package (German) has them as keys of `string_map_data`; the 2026 package (English) has `label_values` lists with `label`/`value` pairs. Both shapes are kept; a key seen only in one language is not marked "not seen since" by a package in another.
- Seven files changed from an object to a list between 2024 and 2026 (`ads_viewed`, `posts_viewed`, `videos_watched`, `posts_you're_not_interested_in`, `liked_posts`, `saved_posts`, `saved_collections`); see `x-changes` in their schemas.
- Only English and German labels have been seen; Dutch and other languages are not covered.
<!-- known gaps by hand: end -->

## Last change

- 2026-11-23: package of 2026-11-23 (en) added: 94 new, 7 changed shape, 0 not seen since an earlier package
