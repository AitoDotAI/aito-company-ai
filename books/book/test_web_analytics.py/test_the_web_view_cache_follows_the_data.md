# The same filter twice: the second is served from the cache

  first request: miss, totals {'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2, 'bots': 1, 'internal': 0}
  same filter again: hit, totals {'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2, 'bots': 1, 'internal': 0}
  another outcome: miss, totals {'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2, 'bots': 1, 'internal': 0}

# A caller changing its answer doesn't change the cached one

  next hit: True, totals {'sessions': 4, 'onward_clicks': 3, 'signup_ctas': 2, 'bots': 1, 'internal': 0}, 5 sessions on the page

# A pull lands (one browser's events dropped): the next request is fresh

  after the pull: miss, totals {'sessions': 3, 'onward_clicks': 2, 'signup_ctas': 1, 'bots': 1, 'internal': 0}
  again: hit, totals {'sessions': 3, 'onward_clicks': 2, 'signup_ctas': 1, 'bots': 1, 'internal': 0}

# A visitor is forgotten: the next request is fresh

  after forgetting the probe's browser: miss, totals {'sessions': 3, 'onward_clicks': 2, 'signup_ctas': 1, 'bots': 0, 'internal': 0}

# The TTL bounds what the fingerprint can't see

  after 901 s: miss, totals {'sessions': 3, 'onward_clicks': 2, 'signup_ctas': 1, 'bots': 0, 'internal': 0}

# An empty window: no drivers, as before

  totals {'sessions': 0, 'onward_clicks': 0, 'signup_ctas': 0, 'bots': 0, 'internal': 0}, drivers None
