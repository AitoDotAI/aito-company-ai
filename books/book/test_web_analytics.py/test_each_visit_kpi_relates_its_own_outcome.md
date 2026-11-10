# web_view(outcome=onward_click)

  drivers relate: {"$on": [{"onward_click": true}, {"$and": [{"likely_bot": false}, {"$and": [{"day": {"$gte": "2026-10-05"}}, {"day": {"$lte": "2026-10-05"}}]}]}]}
  outcome: onward_click

# web_view(outcome=signup_cta)

  drivers relate: {"$on": [{"signup_cta": true}, {"$and": [{"likely_bot": false}, {"$and": [{"day": {"$gte": "2026-10-05"}}, {"day": {"$lte": "2026-10-05"}}]}]}]}
  outcome: signup_cta
  an unknown outcome raises: unknown outcome 'views'; the Web view relates ('onward_click', 'signup_cta')
