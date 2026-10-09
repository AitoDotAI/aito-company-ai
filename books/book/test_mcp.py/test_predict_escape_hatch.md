# predict: ad-hoc question through the escape hatch

request:  {"from": "touches", "limit": 4, "predict": "window", "where": {"channel": "call", "contact_id.segment": "accounting"}}
response: {"hits": [{"$p": 0.33063647749860237, "$value": "0800"}, {"$p": 0.3073510695152008, "$value": "1600"}, {"$p": 0.21219230545545278, "$value": "1215"}, {"$p": 0.1498201475307441, "$value": "other"}], "offset": 0, "total": 4}
