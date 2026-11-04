# log_post_result: posted_at is a plain YYYY-MM-DD, not in the future

The weekday (a scorer feature) is derived from the date as written,
with no timezone conversion, so anything but a plain date is refused.
'2026-10-05junk': posted_at '2026-10-05junk': expected YYYY-MM-DD
'2026-10-05T09:00:00+02:00': posted_at '2026-10-05T09:00:00+02:00': expected YYYY-MM-DD
'5.10.2026': posted_at '5.10.2026': expected YYYY-MM-DD
'2999-01-01': posted_at '2999-01-01' is in the future
