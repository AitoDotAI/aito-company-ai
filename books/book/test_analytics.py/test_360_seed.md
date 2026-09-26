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

[Conversion] rate=0.1447  (good = outcome was conversation / meeting / callback)
    cause channel=call  with=0.3684 without=0.0000 mi=0.1627
    cause window=1600  with=0.2973 without=0.0885 mi=0.0200
    cause weekday=thu  with=0.0571 without=0.1652 mi=0.0033
    lever window (lift 9.54): 1600=0.3077, 0800=0.1455, 1215=0.1212, other=0.0323
[Reach] rate=0.4671  (good = the contact responded at all)
    cause window=1600  with=0.5946 without=0.4248 mi=0.0039
    cause days_since_prev_touch=0-2  with=0.2667 without=0.4889 mi=0.0032
    cause window=other  with=0.3448 without=0.4959 mi=0.0026
    lever channel (lift 1.25): email=0.5000, call=0.4746, linkedin=0.4000
[Meetings] rate=0.0329  (good = a meeting was booked)
    cause channel=call  with=0.0702 without=0.0000 mi=0.0072
    cause days_since_prev_touch=8-21  with=0.0625 without=0.0098 mi=0.0037
    cause weekday=tue  with=0.0769 without=0.0161 mi=0.0030
    lever channel (lift 5.26): call=0.0847, linkedin=0.0286, email=0.0161

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

[Conversion] rate=0.0762  (good = outcome was conversation / meeting / callback)
    why  contact_id.segment=accounting  lift=0.5285
    lever window (lift 7.33): 1600=0.2847, 0800=0.1846, 1215=0.0975, other=0.0389
[Reach] rate=0.5185  (good = the contact responded at all)
    why  contact_id.segment=accounting  lift=1.1099
    lever channel (lift 1.26): email=0.5222, call=0.4189, linkedin=0.4143
[Meetings] rate=0.0252  (good = a meeting was booked)
    why  contact_id.segment=accounting  lift=0.7681
    lever channel (lift 3.86): call=0.0980, linkedin=0.0438, email=0.0254

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

[Conversion] rate=0.2040  (good = outcome was conversation / meeting / callback)
    why  contact_id.segment=erp  lift=1.4954
    why  contact_id.tier=A  lift=0.9186
    lever window (lift 14.06): 1600=0.4903, 1215=0.2515, 0800=0.0611, other=0.0349
[Reach] rate=0.4791  (good = the contact responded at all)
    why  contact_id.tier=A  lift=1.2128
    why  contact_id.segment=erp  lift=0.8208
    lever channel (lift 1.59): call=0.5079, email=0.4355, linkedin=0.3186
[Meetings] rate=0.0396  (good = a meeting was booked)
    why  contact_id.segment=erp  lift=1.5059
    why  contact_id.tier=A  lift=0.7945
    lever channel (lift 7.34): call=0.1908, linkedin=0.0416, email=0.0260
