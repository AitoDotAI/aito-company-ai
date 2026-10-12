# The contact and deal

sc002 Heidi Banks @ mooby-ab; funnel flags: {"ever_touched": false, "ever_reached": false, "ever_conversation": false, "ever_meeting": false}
se001 Prestige Oy stage=qualified last_touch_date=2026-06-03

# First import

rows read: 3
new: 3   changed: 0   unchanged: 0
APPLIED. resequenced: {'touches_updated': 3, 'contacts_updated': 1, 'deals_updated': 1}
2026-09-02T08:40:00 e1         email    out step=1 hour=8 window=0800 company=mooby-ab deal=None
2026-09-09T16:20:00 e3         call     out step=2 hour=16 window=1600 company=mooby-ab deal=se001
2026-09-16T10:00:00 e4         meeting  out step=3 hour=10 window=other company=mooby-ab deal=se001

# The same file again: nothing changes

rows read: 3
new: 0   changed: 0   unchanged: 3
APPLIED. resequenced: {'touches_updated': 0, 'contacts_updated': 0, 'deals_updated': 0}

# A late row (an earlier reply) and an edited row arrive

rows read: 5
new: 2   changed: 1   unchanged: 2
  ~ e1: ['outcome', 'reached']
APPLIED. resequenced: {'touches_updated': 5, 'contacts_updated': 0, 'deals_updated': 0}
2026-08-28T09:15:00 e0         linkedin out step=1 hour=9 window=0800 company=mooby-ab deal=None
2026-09-02T08:40:00 e1         email    out step=2 hour=8 window=0800 company=mooby-ab deal=None
2026-09-03T12:30:00 e2         email    in  step=None hour=12 window=1215 company=mooby-ab deal=None
2026-09-09T16:20:00 e3         call     out step=3 hour=16 window=1600 company=mooby-ab deal=se001
2026-09-16T10:00:00 e4         meeting  out step=4 hour=10 window=other company=mooby-ab deal=se001

# The contact's funnel and the deal moved

{"ever_touched": true, "ever_reached": true, "ever_conversation": true, "ever_meeting": true}
se001 last_touch_date 2026-06-03 -> 2026-09-16

# Weekly KPIs over it

{"by_channel": {}, "calls": 0, "calls_answered_by_person": null, "calls_with_answered_by": 0, "email_replies_in": 0, "emails_out": 0, "engagements": 0, "inbound": 0, "meetings_booked": 0, "meetings_held": 0, "meetings_per_10_first_touches": null, "new_contacts_touched": 0, "week": "2026-W34"}
{"by_channel": {"linkedin": 1}, "calls": 0, "calls_answered_by_person": null, "calls_with_answered_by": 0, "email_replies_in": 0, "emails_out": 0, "engagements": 1, "inbound": 0, "meetings_booked": 0, "meetings_held": 0, "meetings_per_10_first_touches": 0.0, "new_contacts_touched": 1, "week": "2026-W35"}
{"by_channel": {"email": 1}, "calls": 0, "calls_answered_by_person": null, "calls_with_answered_by": 0, "email_replies_in": 1, "emails_out": 1, "engagements": 2, "inbound": 1, "meetings_booked": 0, "meetings_held": 0, "meetings_per_10_first_touches": null, "new_contacts_touched": 0, "week": "2026-W36"}
{"by_channel": {"call": 1}, "calls": 1, "calls_answered_by_person": 1.0, "calls_with_answered_by": 1, "email_replies_in": 0, "emails_out": 0, "engagements": 1, "inbound": 0, "meetings_booked": 1, "meetings_held": 0, "meetings_per_10_first_touches": null, "new_contacts_touched": 0, "week": "2026-W37"}
{"by_channel": {"meeting": 1}, "calls": 0, "calls_answered_by_person": null, "calls_with_answered_by": 0, "email_replies_in": 0, "emails_out": 0, "engagements": 1, "inbound": 0, "meetings_booked": 0, "meetings_held": 1, "meetings_per_10_first_touches": null, "new_contacts_touched": 0, "week": "2026-W38"}
open_deals_by_blocker {"none": 16, "demo_readiness": 9, "budget": 6, "consultant_lock": 5, "timing_mismatch": 2, "no_champion": 2}
lost_by_reason {"not recorded": 179}
