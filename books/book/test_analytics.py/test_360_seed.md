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
    lever window (lift 31.00): 1600=0.2895, 0800=0.1325, 1215=0.0997, other=0.0093
[Reach] rate=0.4671  (good = the contact responded at all)
    cause window=1600  with=0.5946 without=0.4248 mi=0.0039
    cause days_since_prev_touch=0-2  with=0.2667 without=0.4889 mi=0.0032
    cause window=other  with=0.3448 without=0.4959 mi=0.0026
    lever channel (lift 1.25): email=0.4989, call=0.4735, linkedin=0.3981
[Meetings] rate=0.0329  (good = a meeting was booked)
    cause channel=call  with=0.0702 without=0.0000 mi=0.0072
    cause days_since_prev_touch=8-21  with=0.0625 without=0.0098 mi=0.0037
    cause weekday=tue  with=0.0769 without=0.0161 mi=0.0030
    lever channel (lift 64.94): call=0.0689, linkedin=0.0019, email=0.0011

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
    cause channel=call  with=0.2353 without=0.0000 mi=0.0423
    cause weekday=tue  with=0.2143 without=0.0213 mi=0.0173
    cause channel=email  with=0.0000 without=0.1212 mi=0.0108
    lever window (lift 32.27): 1600=0.2654, 0800=0.1671, 1215=0.0779, other=0.0082
[Reach] rate=0.5185  (good = the contact responded at all)
    why  contact_id.segment=accounting  lift=1.1099
    cause channel=email  with=0.6429 without=0.4242 mi=0.0086
    cause channel=call  with=0.3529 without=0.5909 mi=0.0082
    cause days_since_prev_touch=22+  with=0.2500 without=0.5660 mi=0.0082
    lever channel (lift 1.26): email=0.5221, call=0.4187, linkedin=0.4140
[Meetings] rate=0.0252  (good = a meeting was booked)
    why  contact_id.segment=accounting  lift=0.7681
    cause days_since_prev_touch=0-2  with=0.1111 without=0.0000 mi=0.0103
    cause weekday=tue  with=0.0714 without=0.0000 mi=0.0074
    cause channel=call  with=0.0588 without=0.0000 mi=0.0063
    lever channel (lift 80.47): call=0.0796, linkedin=0.0017, email=0.0010

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
    cause channel=call  with=0.8333 without=0.0000 mi=0.3753
    cause window=1600  with=1.0000 without=0.2000 mi=0.1623
    cause channel=email  with=0.0000 without=0.6250 mi=0.1195
    lever window (lift 38.00): 1600=0.3645, 1215=0.1721, 0800=0.0645, other=0.0096
[Reach] rate=0.4791  (good = the contact responded at all)
    why  contact_id.tier=A  lift=1.2128
    why  contact_id.segment=erp  lift=0.8208
    cause window=0800  with=0.1667 without=0.8571 mi=0.1822
    cause channel=call  with=0.8333 without=0.2857 mi=0.0769
    cause window=1600  with=1.0000 without=0.4000 mi=0.0470
    lever channel (lift 1.43): call=0.5073, email=0.4754, linkedin=0.3540
[Meetings] rate=0.0396  (good = a meeting was booked)
    why  contact_id.segment=erp  lift=1.5059
    why  contact_id.tier=A  lift=0.7945
    cause weekday=mon  with=0.5000 without=0.0000 mi=0.1073
    cause window=1600  with=0.3333 without=0.0000 mi=0.0476
    cause channel=call  with=0.1667 without=0.0000 mi=0.0187
    lever channel (lift 97.32): call=0.1080, linkedin=0.0018, email=0.0011
