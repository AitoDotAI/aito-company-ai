# 360: whole pipeline (all contacts)


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

[Conversion] rate=0.2039  (good = outcome was conversation / meeting / callback)
    cause channel=call  with=0.3846 without=0.0000 mi=0.1600
    cause days_since_prev_touch=8-21  with=0.3333 without=0.1579 mi=0.0076
    cause weekday=mon  with=0.1000 without=0.2364 mi=0.0043
    lever window (lift 8.05): 1600=0.3095, 0800=0.2444, 1215=0.2000, other=0.0385
[Reach] rate=0.4934  (good = the contact responded at all)
    cause channel=linkedin  with=0.3214 without=0.5328 mi=0.0049
    cause channel=call  with=0.5513 without=0.4306 mi=0.0026
    cause weekday=wed  with=0.3793 without=0.5207 mi=0.0023
    lever channel (lift 1.65): call=0.5500, email=0.5000, linkedin=0.3333
[Meetings] rate=0.0658  (good = a meeting was booked)
    cause channel=call  with=0.1154 without=0.0000 mi=0.0108
    cause days_since_prev_touch=8-21  with=0.1389 without=0.0351 mi=0.0055
    cause window=0800  with=0.1163 without=0.0374 mi=0.0037
    lever channel (lift 5.75): call=0.1250, linkedin=0.0333, email=0.0217

# 360: segment=accounting


## Aito calls

_predict: {"from": "touches", "predict": "good_outcome", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "accounting"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"good_outcome": true}, {"contact_id.segment": "accounting"}]}}
_recommend: {"from": "touches", "goal": {"good_outcome": true}, "limit": 6, "recommend": "window", "where": {"contact_id.segment": "accounting"}}
_predict: {"from": "touches", "predict": "reached", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "accounting"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"reached": true}, {"contact_id.segment": "accounting"}]}}
_recommend: {"from": "touches", "goal": {"reached": true}, "limit": 6, "recommend": "channel", "where": {"contact_id.segment": "accounting"}}
_predict: {"from": "touches", "predict": "booked", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "accounting"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"booked": true}, {"contact_id.segment": "accounting"}]}}
_recommend: {"from": "touches", "goal": {"booked": true}, "limit": 6, "recommend": "channel", "where": {"contact_id.segment": "accounting"}}

## Derived

[Conversion] rate=0.1028  (good = outcome was conversation / meeting / callback)
    why  contact_id.segment=accounting  lift=0.5068
    cause channel=call  with=0.2308 without=0.0000 mi=0.0254
    cause window=0800  with=0.2500 without=0.0400 mi=0.0153
    cause days_since_prev_touch=first  with=0.2222 without=0.0417 mi=0.0127
    lever window (lift 9.30): 0800=0.3149, 1600=0.2367, 1215=0.1584, other=0.0339
[Reach] rate=0.3626  (good = the contact responded at all)
    why  contact_id.segment=accounting  lift=0.7401
    cause days_since_prev_touch=first  with=0.5556 without=0.2500 mi=0.0146
    cause weekday=wed  with=0.0000 without=0.3793 mi=0.0132
    cause channel=call  with=0.4615 without=0.2500 mi=0.0086
    lever channel (lift 1.65): call=0.5731, email=0.4633, linkedin=0.3472
[Meetings] rate=0.0192  (good = a meeting was booked)
    why  contact_id.segment=accounting  lift=0.2894
    cause weekday=wed  with=0.0000 without=0.0000 mi=0.0072
    cause days_since_prev_touch=0-2  with=0.0000 without=0.0000 mi=0.0070
    cause days_since_prev_touch=22+  with=0.0000 without=0.0000 mi=0.0070
    lever channel (lift 2.78): call=0.1052, linkedin=0.0575, email=0.0378

# 360: segment=erp, tier=A


## Aito calls

_predict: {"from": "touches", "predict": "good_outcome", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"good_outcome": true}, {"$and": [{"contact_id.segment": "erp"}, {"contact_id.tier": "A"}]}]}}
_recommend: {"from": "touches", "goal": {"good_outcome": true}, "limit": 6, "recommend": "window", "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}
_predict: {"from": "touches", "predict": "reached", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"reached": true}, {"$and": [{"contact_id.segment": "erp"}, {"contact_id.tier": "A"}]}]}}
_recommend: {"from": "touches", "goal": {"reached": true}, "limit": 6, "recommend": "channel", "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}
_predict: {"from": "touches", "predict": "booked", "select": ["$p", "$value", "$why"], "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}
_relate: {"from": "touches", "limit": 150, "relate": {"$on": [{"booked": true}, {"$and": [{"contact_id.segment": "erp"}, {"contact_id.tier": "A"}]}]}}
_recommend: {"from": "touches", "goal": {"booked": true}, "limit": 6, "recommend": "channel", "where": {"contact_id.segment": "erp", "contact_id.tier": "A"}}

## Derived

[Conversion] rate=0.2717  (good = outcome was conversation / meeting / callback)
    why  contact_id.segment=erp  lift=1.2235
    why  contact_id.tier=A  lift=1.0799
    cause channel=call  with=0.4167 without=0.0000 mi=0.0720
    cause days_since_prev_touch=8-21  with=0.5000 without=0.1176 mi=0.0344
    cause window=1600  with=0.5000 without=0.1176 mi=0.0344
    lever window (lift 14.34): 1600=0.4398, 1215=0.2287, 0800=0.1296, other=0.0307
[Reach] rate=0.6296  (good = the contact responded at all)
    why  contact_id.segment=erp  lift=1.1936
    why  contact_id.tier=A  lift=1.0896
    cause window=1600  with=1.0000 without=0.4118 mi=0.0860
    cause window=0800  with=0.2500 without=0.7333 mi=0.0627
    cause channel=linkedin  with=0.0000 without=0.6500 mi=0.0339
    lever channel (lift 1.84): call=0.5458, email=0.5236, linkedin=0.2959
[Meetings] rate=0.1051  (good = a meeting was booked)
    why  contact_id.segment=erp  lift=1.3343
    why  contact_id.tier=A  lift=1.1779
    cause window=1600  with=0.3333 without=0.0000 mi=0.0563
    cause channel=call  with=0.1667 without=0.0000 mi=0.0159
    cause channel=email  with=0.0000 without=0.1333 mi=0.0103
    lever channel (lift 10.39): call=0.1497, linkedin=0.0209, email=0.0144
