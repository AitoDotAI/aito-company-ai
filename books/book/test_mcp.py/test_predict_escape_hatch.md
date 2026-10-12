# predict: ad-hoc question through the escape hatch

request:  {"from": "touches", "limit": 4, "predict": "window", "where": {"channel": "call", "contact_id.segment": "accounting"}}
response: {"hits": [{"$p": 0.38064666461309543, "$value": "0800"}, {"$p": 0.35383923867481726, "$value": "1600"}, {"$p": 0.24428730289906578, "$value": "1215"}, {"$p": 0.021226793813021474, "$value": "other"}], "offset": 0, "total": 4}
