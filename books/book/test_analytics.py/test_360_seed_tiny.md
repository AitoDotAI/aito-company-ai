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

[Conversion] rate=0.2353  (good = outcome was conversation / meeting / callback)
    cause channel=call  with=0.5000 without=0.0000 mi=0.1086
    cause days_since_prev_touch=0-2  with=0.5000 without=0.0909 mi=0.0382
    cause weekday=tue  with=0.5000 without=0.0909 mi=0.0382
    lever window (lift 1.88): 1600=0.3742, 1215=0.3322, 0800=0.2484, other=0.1987
[Reach] rate=0.5882  (good = the contact responded at all)
    cause weekday=mon  with=1.0000 without=0.5000 mi=0.0310
    cause window=0800  with=1.0000 without=0.5385 mi=0.0196
    cause days_since_prev_touch=first  with=0.8000 without=0.5000 mi=0.0154
    lever channel (lift 1.25): call=0.6246, email=0.5552, linkedin=0.4993
[Meetings] rate=0.0588  (good = a meeting was booked)
    lever channel (lift 2.25): linkedin=0.1654, call=0.0827, email=0.0735
