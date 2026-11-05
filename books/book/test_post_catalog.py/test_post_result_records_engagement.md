# Log a result with engagement

{"comments": 4, "link_clicks": 17, "post_id": "sp0001", "posted_at": "2026-10-14", "reach_or_views": 900, "reactions": 31, "reposts": 2, "weekday": "wed"}

# Without engagement the columns stay null, not zero

{"comments": null, "link_clicks": null, "reactions": null, "reposts": null}

# Re-logged without counts, the first counts survive

{"comments": 4, "link_clicks": 17, "outcome": "win", "reach_or_views": 1200, "reactions": 31, "reposts": 2}

# A negative count raises

reactions -1: expected a count >= 0

# Engagement restates the outcome, so relate excludes it

relate on won: excludes ['comments', 'link_clicks', 'outcome', 'reactions', 'reposts', 'won']
relate on outcome: excludes ['comments', 'link_clicks', 'outcome', 'reactions', 'reposts', 'won']
