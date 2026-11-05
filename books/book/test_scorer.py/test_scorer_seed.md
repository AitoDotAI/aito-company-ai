# Doctrine-aligned LinkedIn draft (narrate, first comment, manual)


## linkedin: {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "tone": "narrate", "weekday": "wed"}

  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "weekday": "wed"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "lane": "warm", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  P(win)=0.3315  base=0.0771
    why tone=narrate  lift=2.1446
    why ai_made=manual  lift=1.2766
    why $group=[{'link_placement': 'comment'}, {'platform': 'linkedin'}]  lift=1.0914
    why weekday=wed  lift=1.0905
    why platform=linkedin  lift=1.0000
    why link_placement=comment  lift=1.0000
    lever tone: best=narrate  [narrate=0.3785, announce=0.0141, explainer=0.0088, builder=0.0070]
    lever link_placement: best=comment  [comment=0.1456, body=0.0134]
    lever ai_made: best=ai-assisted (SWITCH)  [ai-assisted=0.1666, manual=0.1230, ai=0.0064]

# Its opposite (announce, body link, AI) — should crater


## linkedin: {"ai_made": "ai", "lane": "warm", "link_placement": "body", "tone": "announce", "weekday": "mon"}

  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "weekday": "mon"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "ai", "lane": "warm", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  P(win)=0.0194  base=0.0771
    why $group=[{'link_placement': 'body'}, {'platform': 'linkedin'}]  lift=0.3102
    why ai_made=ai  lift=0.3338
    why tone=announce  lift=0.3438
    why $group=[{'weekday': 'mon'}, {'lane': 'warm'}]  lift=1.3063
    why platform=linkedin  lift=1.0000
    why link_placement=body  lift=1.0000
    lever tone: best=narrate (SWITCH)  [narrate=0.9394, builder=0.0018, explainer=0.0005, announce=0.0003]
    lever link_placement: best=comment (SWITCH)  [comment=0.0499, body=0.0017]
    lever ai_made: best=manual (SWITCH)  [manual=0.3976, ai-assisted=0.1406, ai=0.0005]

# Hacker News show-hn draft


## hackernews: {"ai_made": "manual", "format": "show-hn", "tone": "builder"}

  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _predict: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "predict": "won", "select": ["$p", "$value"], "where": {"platform": "hackernews"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "hackernews"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _recommend: {"from": {"from": "posts", "where": {"outcome": {"$or": ["flop", "modest", "win"]}}}, "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  P(win)=0.0197  base=0.0444
    why $group=[{'format': 'show-hn'}, {'platform': 'hackernews'}]  lift=0.3102
    why tone=builder  lift=0.3667
    why ai_made=manual  lift=1.2766
    why platform=hackernews  lift=1.0000
    why format=show-hn  lift=1.0000
    lever tone: best=narrate (SWITCH)  [narrate=0.4152, builder=0.0123, explainer=0.0004, announce=0.0003]
    lever link_placement: best=n_a  [n_a=0.8381]
    lever ai_made: best=ai-assisted (SWITCH)  [ai-assisted=0.3545, manual=0.2824, ai=0.0008]
