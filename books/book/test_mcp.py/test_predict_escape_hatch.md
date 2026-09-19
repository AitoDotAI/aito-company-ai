# predict: ad-hoc question through the escape hatch

request:  {"from": "touches", "limit": 4, "predict": "window", "where": {"channel": "call", "contact_id.segment": "accounting"}}
response: {"hits": [{"$p": 0.329507149145763, "$value": "1600"}, {"$p": 0.2979378178210701, "$value": "0800"}, {"$p": 0.21291174561031004, "$value": "1215"}, {"$p": 0.15964328742285683, "$value": "other"}], "offset": 0, "total": 4}
