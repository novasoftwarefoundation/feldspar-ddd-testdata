# facebook: limits of the known structure

A structure is only as complete as the packages it came from: a file, key or label that no package has shown yet is not in it. This file is rewritten by `ddd.py add`; the part between the "by hand" markers is kept.

## Coverage

- Packages: 1, export dates 2024-09-02; languages en
- File patterns seen: 14 (json 14)
- No media files (photos, videos, audio) in any package yet.
- Lists that were empty in every package, so their items are unknown: 4
  - `fb_example/ad_preferences.json .label_values[].vec`
  - `fb_example/ad_preferences.json .media`
  - `fb_example/story_views_in_past_7_days.json .media`
  - `fb_example/subscription_for_no_ads.json .media`

## Left out

Names, keys and labels the extractor was not sure about. They were replaced by a placeholder or dropped; only the place and the count are kept.

- 2 × label not kept (unsure it is the platform's wording): fb_example/ad_preferences.json.label_values[].label

## Known gaps

Files the platform's donation scripts read that no package has shown yet: 49
- `ads.json`
- `ads_feedback_activity.json`
- `ads_personalization_consent.json`
- `autofill_information.json`
- `contacts_sync_settings.json`
- `content_that_has_been_shown_to_you_in_your_feed.json`
- `controls.json`
- `event_invitations.json`
- `fundraiser_posts_you_likely_viewed.json`
- `group_posts_and_comments.json`
- `instant_games.json`
- `instant_games_usage_data.json`
- `link_history.json`
- `meta_avatars_post_backgrounds.json`
- `navigation_bar_activity.json`
- `notification_of_meta_privacy_policy_update.json`
- `notifications.json`
- `pages_and_profiles_you_follow.json`
- `pages_you_ve_liked.json`
- `payment_history.json`
- `people_and_friends.json`
- `people_you_may_know.json`
- `primary_location.json`
- `primary_public_location.json`
- `profile_information.json`
- `profile_update_history.json`
- `profile_visits.json`
- `received_friend_requests.json`
- `shows_you_have_watched.json`
- `timezone.json`
- `who_you_ve_followed.json`
- `your_activity_off_meta_technologies.json`
- `your_answers_to_membership_questions.json`
- `your_avatar.json`
- `your_comments_in_groups.json`
- `your_contributions.json`
- `your_event_invitation_links.json`
- `your_event_responses.json`
- `your_events.json`
- `your_friends.json`
- `your_fundraiser_donations_information.json`
- `your_group_membership_activity.json`
- `your_page_or_groups_badges.json`
- `your_privacy_jurisdiction.json`
- `your_recently_followed_history.json`
- `your_recently_used_emojis.json`
- `your_saved_items.json`
- `your_transaction_survey_information.json`
- `your_uncategorized_photos.json`

<!-- known gaps by hand: start -->
- The only package so far is a flat example folder (`fb_example/`), not Facebook's own folder layout: file names and JSON shapes are Facebook's, the folders are not.
- No package with Facebook's own layout, messages or media has been seen yet.
<!-- known gaps by hand: end -->

## Last change

- 2024-09-02: package of 2024-09-02 (en) added: 14 new, 0 changed shape, 0 not seen since an earlier package
