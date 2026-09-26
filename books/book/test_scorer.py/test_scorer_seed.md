# Doctrine-aligned LinkedIn draft (narrate, first comment, manual)


## linkedin: {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "tone": "narrate", "weekday": "wed"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "weekday": "wed"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "lane": "warm", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  P(win)=0.1925  base=0.0771
    why tone=narrate  lift=1.5102
    why weekday=wed  lift=1.1008
    why $group=[{'link_placement': 'comment'}, {'platform': 'linkedin'}]  lift=1.0914
    why platform=linkedin  lift=1.0000
    why link_placement=comment  lift=1.0000
    why ai_made=manual  lift=1.0000
    lever tone: best=narrate  [narrate=0.8207, announce=0.3175, explainer=0.2020, builder=0.1580]
    lever link_placement: best=comment  [comment=0.3255, body=0.1921]
    lever ai_made: best=manual  [manual=0.7457, ai-assisted=0.5840, ai=0.3059]

# Its opposite (announce, body link, AI) — should crater


## linkedin: {"ai_made": "ai", "lane": "warm", "link_placement": "body", "tone": "announce", "weekday": "mon"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "weekday": "mon"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "ai", "lane": "warm", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  P(win)=0.0229  base=0.0771
    why $group=[{'link_placement': 'body'}, {'platform': 'linkedin'}]  lift=0.3102
    why tone=announce  lift=0.5313
    why weekday=mon  lift=1.3417
    why link_placement=body  lift=1.0000
    why platform=linkedin  lift=1.0000
    why ai_made=ai  lift=1.0000
    lever tone: best=builder (SWITCH)  [builder=1.0000, explainer=1.0000, narrate=0.9999, announce=0.9999]
    lever link_placement: best=comment (SWITCH)  [comment=0.3572, body=0.0848]
    lever ai_made: best=ai  [ai=0.9637, manual=0.9558, ai-assisted=0.8330]

# Hacker News show-hn draft


## hackernews: {"ai_made": "manual", "format": "show-hn", "tone": "builder"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "hackernews"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "hackernews"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  P(win)=0.0192  base=0.0305
    why $group=[{'format': 'show-hn'}, {'platform': 'hackernews'}]  lift=0.3102
    why tone=builder  lift=0.3102
    why ai_made=manual  lift=1.0249
    why platform=hackernews  lift=1.0000
    why format=show-hn  lift=1.0000
    lever tone: best=builder  [builder=0.9995, narrate=0.9984, explainer=0.9982, announce=0.9980]
    lever link_placement: best=n_a  [n_a=0.9999]
    lever ai_made: best=ai (SWITCH)  [ai=0.9828, ai-assisted=0.9510, manual=0.8910]
