# default call

request: {'from': 'changelog', 'where': {}, 'orderBy': {'$desc': 'at'}, 'limit': 50}
count: 10000, returned: 50
first: 2026-01-07T22:39:00+00:00 change 9999

# a caller asking for more than the cap is clamped

request: {'from': 'changelog', 'where': {}, 'orderBy': {'$desc': 'at'}, 'limit': 1000}
returned: 1000

# entity filter and since window stay server-side

request: {'from': 'changelog', 'where': {'entity': 'deal', 'at': {'$gte': '2026-01-07T17:39:00+00:00'}}, 'orderBy': {'$desc': 'at'}, 'limit': 20}
count: 101, returned: 20
