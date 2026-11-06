# First result with upvotes and trials, then a re-log with only reach

{"outcome": "win", "reach_or_views": 1500, "trials": 3, "upvotes": 12}

# A first result without them stores null, not 0

{"trials": null, "upvotes": null}

# Given explicitly, 0 is stored as 0, and a negative raises

upvotes=0
trials -2: expected a count >= 0
