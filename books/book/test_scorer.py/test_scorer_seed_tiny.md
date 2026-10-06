# Scorer on the tiny dataset (cold-start honesty)


## linkedin: {"link_placement": "comment", "tone": "narrate"}

  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value", "$why"], "where": {"link_placement": "comment", "platform": "linkedin", "tone": "narrate"}}
  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"link_placement": "comment", "platform": "linkedin"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"platform": "linkedin", "tone": "narrate"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"link_placement": "comment", "platform": "linkedin", "tone": "narrate"}}
  P(win)=0.2650  base=0.2000
    why tone=narrate  lift=1.2599
