# Bots

  / /sitemap/sitemap.xml: likely_bot=True
  /blog/ /wp-sitemap.xml: likely_bot=True
  / /pricing/: likely_bot=False

# Drop-off leads with where visits end more often; the rest is kept apart

  ends: [('page:/blog/', 1.377), ('page:/docs/', 1.236)]
  continues from: [('page:/', 0.113)]

# Thin is judged on visits, not steps: one visitor reloading stays thin

  page:/x/: 6 steps, 1 visit, thin True
