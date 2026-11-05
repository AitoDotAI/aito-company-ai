# web_traffic for the day (bots excluded)

{
 "bots": 1,
 "days": [
  {
   "day": "2026-10-05",
   "onward_clicks": 3,
   "sessions": 4,
   "signup_ctas": 2,
   "views": 9
  }
 ],
 "posts": [
  {
   "link_basis": "utm_campaign",
   "post_id": "<li-post>",
   "sessions": 1
  },
  {
   "link_basis": "referrer_day",
   "post_id": "<hn-post>",
   "sessions": 1
  }
 ],
 "since": "2026-10-05",
 "top_landing": [
  [
   "/",
   2
  ],
  [
   "/blog/every-screen-a-decision/",
   1
  ],
  [
   "/docs/",
   1
  ]
 ],
 "top_sources": [
  [
   "social",
   2
  ],
  [
   "direct",
   1
  ],
  [
   "organic",
   1
  ]
 ],
 "until": "2026-10-05"
}

# web_paths: landing -> next, by source and device

{
 "paths": [
  {
   "device_class": "desktop",
   "landing_path": "/",
   "next_path": null,
   "sessions": 1,
   "source": "social",
   "week": "2026-W41"
  },
  {
   "device_class": "desktop",
   "landing_path": "/",
   "next_path": "ecommerce.aito.ai/cart",
   "sessions": 1,
   "source": "direct",
   "week": "2026-W41"
  },
  {
   "device_class": "mobile",
   "landing_path": "/blog/every-screen-a-decision/",
   "next_path": "/pricing/",
   "sessions": 1,
   "source": "social",
   "week": "2026-W41"
  },
  {
   "device_class": "unknown",
   "landing_path": "/docs/",
   "next_path": "/docs/api/v2/quickstart/",
   "sessions": 1,
   "source": "organic",
   "week": "2026-W41"
  }
 ],
 "since": "2026-10-05",
 "until": "2026-10-05"
}

# The weekly KPIs carry the web line

{"web_onward_click_rate": 0.75, "web_sessions": 4, "week": "2026-W41"}

# A campaign slug is unique across posts

'ecom-screen': utm_campaign 'ecom-screen'
'Ecom Screen': utm_campaign 'Ecom Screen': expected a lowercase slug (a-z, 0-9, -)

# Dogfood: the next page, predicted from how the visitor arrived

request:  {"from": "web_sessions", "limit": 5, "predict": "next_path", "select": ["$p", "$value", "$why"], "where": {"device_class": "mobile", "landing_path": "/blog/every-screen-a-decision/", "likely_bot": false, "source": "social"}}
response: {"hits": [{"$p": 0.44755786478761383, "$value": "/pricing/", "$why": {"factors": [{"proposition": {"next_path": {"$has": "/pricing/"}}, "type": "baseP", "value": 0.3333333333333333}, {"factors": [{"name": "exclusiveness", "type": "normalizer", "value": 1.122124213202473}, {"name": "trueFalseExclusiveness", "type": "normalizer", "value": 1.0}], "type": "product"}, {"proposition": {"source": "social"}, "type": "relatedPropositionLift", "value": 1.0}, {"proposition": {"landing_path": "/blog/every-screen-a-decision/"}, "type": "relatedPropositionLift", "value": 1.1856311014966876}, {"proposition":
