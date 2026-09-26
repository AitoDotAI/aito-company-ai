# Sales funnel: all contacts


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

  Contacts: 60  rate_of_top=1.0000
  Touched: 46  rate_of_top=0.7667  (0.7667 from prev)
  Reached: 35  rate_of_top=0.5833  (0.7609 from prev)
  Conversation: 15  rate_of_top=0.2500  (0.4286 from prev)
  Meeting booked: 4  rate_of_top=0.0667  (0.2667 from prev)
  leak: {'into': 'Meeting booked', 'conversion': 0.26666666666666666}
  outlook P(Meeting booked) = 0.0806
    cause country=Netherlands with=0.5000 without=0.0517 mi=0.0138
    cause role=COO with=0.5000 without=0.0517 mi=0.0138
    cause segment=consultancy with=0.5000 without=0.0517 mi=0.0138
    lever source: referral=0.2499, warm=0.1600, trigger=0.0768, cold=0.0454

# Sales funnel: segment=accounting


## Aito calls

_query: {"from": "contacts", "limit": 0, "where": {"segment": "accounting"}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_touched": true, "segment": "accounting"}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_reached": true, "segment": "accounting"}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_conversation": true, "segment": "accounting"}}
_query: {"from": "contacts", "limit": 0, "where": {"ever_meeting": true, "segment": "accounting"}}
_predict: {"from": "contacts", "predict": "ever_meeting", "select": ["$p", "$value", "$why"], "where": {"segment": "accounting"}}
_relate: {"from": "contacts", "limit": 150, "relate": {"$on": [{"ever_meeting": true}, {"segment": "accounting"}]}}
_recommend: {"from": "contacts", "goal": {"ever_meeting": true}, "limit": 8, "recommend": "source", "where": {"segment": "accounting"}}

## Derived

  Contacts: 26  rate_of_top=1.0000
  Touched: 16  rate_of_top=0.6154  (0.6154 from prev)
  Reached: 13  rate_of_top=0.5000  (0.8125 from prev)
  Conversation: 4  rate_of_top=0.1538  (0.3077 from prev)
  Meeting booked: 1  rate_of_top=0.0385  (0.2500 from prev)
  leak: {'into': 'Meeting booked', 'conversion': 0.25}
  outlook P(Meeting booked) = 0.0597
    why segment=accounting lift=0.7449
    lever source: referral=0.5841, trigger=0.1380, cold=0.0888, warm=0.0733
