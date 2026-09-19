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
  Signed up: 220  rate_of_top=0.3667  (0.3667 from prev)
  Started trial: 97  rate_of_top=0.1617  (0.4409 from prev)
  Converted to paid: 35  rate_of_top=0.0583  (0.3608 from prev)
  leak: {'into': 'Converted to paid', 'conversion': 0.36082474226804123}
  outlook P(Converted to paid) = 0.0598
    cause source=referral with=0.1486 without=0.0456 mi=0.0039
    cause device=mobile with=0.0320 without=0.0735 mi=0.0014
    cause source=social with=0.0125 without=0.0654 mi=0.0012
    lever source: referral=0.1579, organic=0.0714, paid_search=0.0517, direct=0.0417, social=0.0244

# Website funnel: source=referral


## Aito calls

_query: {"from": "sessions", "limit": 0, "where": {"source": "referral"}}
_query: {"from": "sessions", "limit": 0, "where": {"signed_up": true, "source": "referral"}}
_query: {"from": "sessions", "limit": 0, "where": {"source": "referral", "started_trial": true}}
_query: {"from": "sessions", "limit": 0, "where": {"converted_paid": true, "source": "referral"}}
_predict: {"from": "sessions", "predict": "converted_paid", "select": ["$p", "$value", "$why"], "where": {"source": "referral"}}
_relate: {"from": "sessions", "limit": 150, "relate": {"$on": [{"converted_paid": true}, {"source": "referral"}]}}

## Derived

  Visitors: 74  rate_of_top=1.0000
  Signed up: 35  rate_of_top=0.4730  (0.4730 from prev)
  Started trial: 18  rate_of_top=0.2432  (0.5143 from prev)
  Converted to paid: 11  rate_of_top=0.1486  (0.6111 from prev)
  leak: {'into': 'Signed up', 'conversion': 0.47297297297297297}
  outlook P(Converted to paid) = 0.1252
    why source=referral lift=2.0450
    cause landing_page=/demo with=0.4211 without=0.0545 mi=0.0770
    cause device=tablet with=0.3333 without=0.1129 mi=0.0083
    cause country=Germany with=0.3750 without=0.1212 mi=0.0076

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

  Visitors: 219  rate_of_top=1.0000
  Signed up: 80  rate_of_top=0.3653  (0.3653 from prev)
  Started trial: 23  rate_of_top=0.1050  (0.2875 from prev)
  Converted to paid: 7  rate_of_top=0.0320  (0.3043 from prev)
  leak: {'into': 'Started trial', 'conversion': 0.2875}
  outlook P(Converted to paid) = 0.0347
    why device=mobile lift=0.5802
    cause landing_page=/pricing with=0.1190 without=0.0113 mi=0.0081
    cause source=referral with=0.0857 without=0.0217 mi=0.0027
    cause landing_page=/blog with=0.0000 without=0.0409 mi=0.0019
    lever source: referral=0.1486, organic=0.0572, paid_search=0.0536, direct=0.0483, social=0.0294
