# Website funnel, tiny dataset (cold-start honesty)


## Aito calls

_query: {"from": "sessions", "limit": 0, "where": {}}
_query: {"from": "sessions", "limit": 0, "where": {"signed_up": true}}
_query: {"from": "sessions", "limit": 0, "where": {"started_trial": true}}
_query: {"from": "sessions", "limit": 0, "where": {"converted_paid": true}}
_predict: {"from": "sessions", "predict": "converted_paid", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "sessions", "limit": 150, "relate": {"converted_paid": true}}
_recommend: {"from": "sessions", "goal": {"converted_paid": true}, "limit": 8, "recommend": "source", "where": {}}

## Derived

  Visitors: 30  rate_of_top=1.0000
  Signed up: 12  rate_of_top=0.4000  (0.4000 from prev)
  Started trial: 5  rate_of_top=0.1667  (0.4167 from prev)
  Converted to paid: 1  rate_of_top=0.0333  (0.2000 from prev)
  leak: {'into': 'Converted to paid', 'conversion': 0.2}
  outlook P(Converted to paid) = 0.0625
    cause source=referral with=0.2500 without=0.0000 mi=0.0328
    cause landing_page=/pricing with=0.1111 without=0.0000 mi=0.0124
    cause device=desktop with=0.1000 without=0.0000 mi=0.0112
    lever source: referral=0.3326, direct=0.2489, social=0.1245, organic=0.0905, paid_search=0.0905

# Sales funnel, tiny dataset


## Aito calls

_query: {"from": "contacts", "limit": 0, "where": {}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_touched": true}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_reached": true}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_conversation": true}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_meeting": true}}
_predict: {"from": "contacts", "predict": "ever_meeting", "select": ["$p", "$value", "$why"], "where": {}}
_relate: {"from": "contacts", "limit": 150, "relate": {"ever_meeting": true}}
_recommend: {"from": "contacts", "goal": {"ever_meeting": true}, "limit": 8, "recommend": "source", "where": {}}

## Derived

  Contacts: 10  rate_of_top=1.0000
  Touched: 5  rate_of_top=0.5000  (0.5000 from prev)
  Reached: 5  rate_of_top=0.5000  (1.0000 from prev)
  Conversation: 3  rate_of_top=0.3000  (0.6000 from prev)
  Meeting booked: 0  rate_of_top=0.0000  (0.0000 from prev)
  leak: {'into': 'Meeting booked', 'conversion': 0.0}
  outlook P(Meeting booked) = 0.0833
    lever source: referral=0.2196, trigger=0.2196, warm=0.1317, cold=0.0941
