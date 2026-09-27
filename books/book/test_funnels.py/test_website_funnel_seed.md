# Website funnel: all sessions


## Aito calls

_query: {"from": "sessions", "limit": 0, "where": {}}
_query: {"from": "sessions", "limit": 0, "where": {"signed_up": true}}
_query: {"from": "sessions", "limit": 0, "where": {"started_trial": true}}
_query: {"from": "sessions", "limit": 0, "where": {"converted_paid": true}}
_predict: {"from": "sessions", "predict": "converted_paid", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "sessions", "limit": 150, "relate": {"converted_paid": true}}
_recommend: {"from": "sessions", "goal": {"converted_paid": true}, "limit": 8, "recommend": "source", "where": {}}

## Derived

  Visitors: 600  rate_of_top=1.0000
  Signed up: 221  rate_of_top=0.3683  (0.3683 from prev)
  Started trial: 98  rate_of_top=0.1633  (0.4434 from prev)
  Converted to paid: 36  rate_of_top=0.0600  (0.3673 from prev)
  leak: {'into': 'Converted to paid', 'conversion': 0.3673469387755102}
  outlook P(Converted to paid) = 0.0615
    cause source=referral with=0.1410 without=0.0479 mi=0.0029
    cause device=mobile with=0.0321 without=0.0759 mi=0.0015
    cause landing_page=/blog with=0.0238 without=0.0696 mi=0.0012
    lever source: referral=0.1500, organic=0.0718, paid_search=0.0520, direct=0.0435, social=0.0357

# Website funnel: source=referral


## Aito calls

_query: {"from": "sessions", "limit": 0, "where": {"source": "referral"}}
_query: {"from": "sessions", "limit": 0, "where": {"signed_up": true, "source": "referral"}}
_query: {"from": "sessions", "limit": 0, "where": {"source": "referral", "started_trial": true}}
_query: {"from": "sessions", "limit": 0, "where": {"converted_paid": true, "source": "referral"}}
_predict: {"from": "sessions", "predict": "converted_paid", "select": ["$p", "$value", "$why"], "where": {"source": "referral"}}
_relate: {"from": "sessions", "limit": 150, "relate": {"$on": [{"converted_paid": true}, {"source": "referral"}]}}

## Derived

  Visitors: 78  rate_of_top=1.0000
  Signed up: 36  rate_of_top=0.4615  (0.4615 from prev)
  Started trial: 19  rate_of_top=0.2436  (0.5278 from prev)
  Converted to paid: 11  rate_of_top=0.1410  (0.5789 from prev)
  leak: {'into': 'Signed up', 'conversion': 0.46153846153846156}
  outlook P(Converted to paid) = 0.1206
    why source=referral lift=1.9221

# Website funnel: device=mobile (the planted trial leak)


## Aito calls

_query: {"from": "sessions", "limit": 0, "where": {"device": "mobile"}}
_query: {"from": "sessions", "limit": 0, "where": {"device": "mobile", "signed_up": true}}
_query: {"from": "sessions", "limit": 0, "where": {"device": "mobile", "started_trial": true}}
_query: {"from": "sessions", "limit": 0, "where": {"converted_paid": true, "device": "mobile"}}
_predict: {"from": "sessions", "predict": "converted_paid", "select": ["$p", "$value", "$why"], "where": {"device": "mobile"}}
_relate: {"from": "sessions", "limit": 150, "relate": {"$on": [{"converted_paid": true}, {"device": "mobile"}]}}
_recommend: {"from": "sessions", "goal": {"converted_paid": true}, "limit": 8, "recommend": "source", "where": {"device": "mobile"}}

## Derived

  Visitors: 218  rate_of_top=1.0000
  Signed up: 81  rate_of_top=0.3716  (0.3716 from prev)
  Started trial: 23  rate_of_top=0.1055  (0.2840 from prev)
  Converted to paid: 7  rate_of_top=0.0321  (0.3043 from prev)
  leak: {'into': 'Started trial', 'conversion': 0.2839506172839506}
  outlook P(Converted to paid) = 0.0348
    why device=mobile lift=0.5676
    lever source: referral=0.1413, organic=0.0592, paid_search=0.0554, direct=0.0516, social=0.0374
