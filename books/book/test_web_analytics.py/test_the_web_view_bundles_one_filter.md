# Everything on the day

  totals: {'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2, 'bots': 1}
  days: [{'day': '2026-10-05', 'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2}]
  facets: {'source': ['direct', 'organic', 'social'], 'device_class': ['desktop', 'mobile', 'unknown'], 'utm_campaign': ['ecom-screen'], 'landing_path': ['/', '/blog/every-screen-a-decision/', '/docs/']}
  drivers request: {"from": "web_sessions", "limit": 300, "relate": {"$on": [{"onward_click": true}, {"$and": [{"likely_bot": false}, {"$and": [{"day": {"$gte": "2026-10-05"}}, {"day": {"$lte": "2026-10-05"}}]}]}]}}
  sessions: 5 rows, page of 5
  thin below: 5 sessions
  first row fields: ['country', 'day', 'device_class', 'engaged_seconds', 'hour', 'landing_path', 'likely_bot', 'next_path', 'onward_click', 'referrer_domain', 'signup_cta', 'source', 'views']

# One source, one landing page

  filter source=direct landing=/
  totals: {'sessions': 1, 'onward_clicks': 1, 'signup_ctas': 1, 'bots': 0}
  facets still list every source: True
  drivers where: {"$and": [{"day": {"$gte": "2026-10-05"}}, {"day": {"$lte": "2026-10-05"}}, {"source": "direct"}, {"landing_path": "/"}], "likely_bot": false}
  next_paths: {'request': {'from': 'web_sessions', 'where': {'landing_path': '/', 'likely_bot': False, 'source': 'direct'}, 'predict': 'next_path', 'select': ['$p', '$value', '$why'], 'limit': 5}, 'hits': [{'value': 'ecommerce.aito.ai/cart', 'p': 0.4518814380842081}, {'value': '/docs/api/v2/quickstart/', 'p': 0.27405928095789595}, {'value': '/pricing/', 'p': 0.27405928095789595}]}
