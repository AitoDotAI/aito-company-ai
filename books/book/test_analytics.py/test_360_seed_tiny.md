# 360: whole pipeline, tiny dataset (cold-start honesty)


## Aito calls

_predict: {"from": "touches", "predict": "good_outcome", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "touches", "limit": 150, "relate": {"good_outcome": true}}
_recommend: {"from": "touches", "goal": {"good_outcome": true}, "limit": 6, "recommend": "window", "where": {}}
_predict: {"from": "touches", "predict": "reached", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "touches", "limit": 150, "relate": {"reached": true}}
_recommend: {"from": "touches", "goal": {"reached": true}, "limit": 6, "recommend": "channel", "where": {}}
_predict: {"from": "touches", "predict": "booked", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "touches", "limit": 150, "relate": {"booked": true}}
_recommend: {"from": "touches", "goal": {"booked": true}, "limit": 6, "recommend": "channel", "where": {}}

## Derived

[Conversion] rate=0.2941  (good = outcome was conversation / meeting / callback)
    cause weekday=tue  with=0.6667 without=0.0000 mi=0.2287
    cause channel=call  with=0.5714 without=0.0000 mi=0.1432
    cause window=0800  with=0.6667 without=0.1667 mi=0.0382
    lever window (lift 4.22): 0800=0.5989, 1215=0.3989, 1600=0.3324, other=0.1420
[Reach] rate=0.5294  (good = the contact responded at all)
    cause weekday=thu  with=0.1667 without=0.7778 mi=0.1198
    cause weekday=tue  with=0.8333 without=0.3333 mi=0.0552
    cause weekday=mon  with=1.0000 without=0.5000 mi=0.0134
    lever channel (lift 2.51): email=0.6246, call=0.5552, linkedin=0.2492
[Meetings] rate=0.2353  (good = a meeting was booked)
    cause weekday=tue  with=0.5000 without=0.0000 mi=0.1086
    cause window=0800  with=0.6667 without=0.0833 mi=0.0889
    cause channel=call  with=0.4286 without=0.0000 mi=0.0621
    lever channel (lift 3.57): call=0.4437, linkedin=0.2484, email=0.1242
