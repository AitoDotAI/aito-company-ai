# Flags

  24f1ed…: likely_internal=False, likely_bot=False
  5ba474…: likely_internal=False, likely_bot=False
  426f03…: likely_internal=False, likely_bot=False
  f2809a…: likely_internal=True, likely_bot=False
  346000…: likely_internal=True, likely_bot=False

# The pull counts them apart

  sessions 5, bots 0, internal 2

# A row from before the column counts; the internal ones don't

  web_traffic: [{'day': '2026-10-05', 'sessions': 4, 'views': 8, 'onward_clicks': 4, 'signup_ctas': 0}], bots 0, internal 2
  web_view totals: {'sessions': 4, 'onward_clicks': 4, 'signup_ctas': 0, 'bots': 0, 'internal': 2}
  web_kpis(pricing_page): 4 sessions, 4 with it
  web_paths: 4 sessions
  web_steps: 6 steps (2 per human visit stored by the pull)
  web_visitors: 3 visitors (the old row is a copy of one of them)

# Any other value raises, with the event

  unknown internal value 'yes' on {'$insert_id': 'ins-1759700000020-2026-10-05 10:20:00-/', 
