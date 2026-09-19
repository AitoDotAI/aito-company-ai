# Doctrine-aligned LinkedIn draft (narrate, first comment, manual)


## linkedin: {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "tone": "narrate", "weekday": "wed"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "lane": "warm", "link_placement": "comment", "platform": "linkedin", "weekday": "wed"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "lane": "warm", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "comment", "platform": "linkedin", "tone": "narrate", "weekday": "wed"}}
  P(win)=0.5533  base=0.2026
    why tone=narrate  lift=1.8512
    why $group=[{'link_placement': 'comment'}, {'platform': 'linkedin'}]  lift=1.5790
    why weekday=wed  lift=1.1720
    why ai_made=manual  lift=1.1488
    lever tone: best=builder (SWITCH)  [builder=0.9994, announce=0.9976, explainer=0.9976, narrate=0.0000]
    lever link_placement: best=comment  [comment=0.9974, body=0.9589]
    lever ai_made: best=ai (SWITCH)  [ai=0.9801, ai-assisted=0.9801, manual=0.0000]

# Its opposite (announce, body link, AI) — should crater


## linkedin: {"ai_made": "ai", "lane": "warm", "link_placement": "body", "tone": "announce", "weekday": "mon"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "linkedin"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "linkedin"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "ai", "lane": "warm", "link_placement": "body", "platform": "linkedin", "weekday": "mon"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "ai", "lane": "warm", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"lane": "warm", "link_placement": "body", "platform": "linkedin", "tone": "announce", "weekday": "mon"}}
  P(win)=0.0192  base=0.2026
    why tone=announce  lift=0.2429
    why ai_made=ai  lift=0.3858
    why link_placement=body  lift=0.6501
    why $group=[{'link_placement': 'body'}, {'platform': 'linkedin'}, {'weekday': 'mon'}]  lift=1.0726
    why platform=linkedin  lift=1.0000
    lever tone: best=narrate (SWITCH)  [narrate=0.9907, builder=0.9903, explainer=0.9392, announce=0.0210]
    lever link_placement: best=comment (SWITCH)  [comment=0.2983, body=0.0102]
    lever ai_made: best=ai-assisted (SWITCH)  [ai-assisted=0.4566, ai=0.4514, manual=0.4435]

# Hacker News show-hn draft


## hackernews: {"ai_made": "manual", "format": "show-hn", "tone": "builder"}

  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value", "$why"], "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _predict: {"from": "posts", "predict": "won", "select": ["$p", "$value"], "where": {"platform": "hackernews"}}
  _query: {"from": "posts", "limit": 5000, "where": {"platform": "hackernews"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "tone", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "link_placement", "where": {"ai_made": "manual", "format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  _recommend: {"from": "posts", "goal": {"won": true}, "limit": 8, "recommend": "ai_made", "where": {"format": "show-hn", "platform": "hackernews", "tone": "builder"}}
  P(win)=0.2723  base=0.1562
    why ai_made=manual  lift=1.4699
    why $group=[{'format': 'show-hn'}, {'platform': 'hackernews'}]  lift=1.1868
    why format=show-hn  lift=1.0000
    why platform=hackernews  lift=1.0000
    lever tone: best=announce (SWITCH)  [announce=0.3140, explainer=0.3140, builder=0.0072, narrate=0.0050]
    lever link_placement: best=n_a  [n_a=0.0000]
    lever ai_made: best=ai (SWITCH)  [ai=0.0021, manual=0.0016, ai-assisted=0.0012]
