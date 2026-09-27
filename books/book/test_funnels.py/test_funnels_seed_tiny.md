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
    cause source=referral with=0.2000 without=0.0000 mi=0.0211
    cause device=desktop with=0.1111 without=0.0000 mi=0.0124
    cause landing_page=/pricing with=0.1111 without=0.0000 mi=0.0124
    lever source: referral=0.2851, direct=0.1991, social=0.1422, paid_search=0.0996, organic=0.0905

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
  Touched: 7  rate_of_top=0.7000  (0.7000 from prev)
  Reached: 5  rate_of_top=0.5000  (0.7143 from prev)
  Conversation: 4  rate_of_top=0.4000  (0.8000 from prev)
  Meeting booked: 3  rate_of_top=0.3000  (0.7500 from prev)
  leak: {'into': 'Touched', 'conversion': 0.7}
  outlook P(Meeting booked) = 0.3333
    cause ai_lifecycle=operating with=1.0000 without=0.2222 mi=0.0409
    cause country=Germany with=1.0000 without=0.2222 mi=0.0409
    cause role=Finance Manager with=1.0000 without=0.2222 mi=0.0409
    lever source: trigger=0.6630, cold=0.3978, referral=0.3315, warm=0.2473
