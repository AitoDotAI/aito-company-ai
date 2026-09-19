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

  Contacts: 50  rate_of_top=1.0000
  Touched: 39  rate_of_top=0.7800  (0.7800 from prev)
  Reached: 30  rate_of_top=0.6000  (0.7692 from prev)
  Conversation: 20  rate_of_top=0.4000  (0.6667 from prev)
  Meeting booked: 8  rate_of_top=0.1600  (0.4000 from prev)
  leak: {'into': 'Meeting booked', 'conversion': 0.4}
  outlook P(Meeting booked) = 0.1731
    cause role=CEO with=0.5000 without=0.1136 mi=0.0236
    cause segment=erp with=0.3636 without=0.1026 mi=0.0163
    cause tier=C with=0.0476 without=0.2414 mi=0.0125
    lever source: referral=0.2999, cold=0.2000, trigger=0.1817, warm=0.1764

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

  Contacts: 14  rate_of_top=1.0000
  Touched: 9  rate_of_top=0.6429  (0.6429 from prev)
  Reached: 7  rate_of_top=0.5000  (0.7778 from prev)
  Conversation: 3  rate_of_top=0.2143  (0.4286 from prev)
  Meeting booked: 0  rate_of_top=0.0000  (0.0000 from prev)
  leak: {'into': 'Meeting booked', 'conversion': 0.0}
  outlook P(Meeting booked) = 0.0522
    why segment=accounting lift=0.3102
    lever source: referral=0.2723, cold=0.2199, warm=0.1981, trigger=0.1744
