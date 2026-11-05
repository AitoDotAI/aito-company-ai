# relate on onward_click: the fields left as drivers

drivers: ['country', 'device_class', 'hour', 'landing_path', 'referrer_domain', 'source', 'utm_campaign', 'utm_medium', 'utm_source', 'weekday']
where: {"$and": [{"day": {"$gte": "2026-10-05"}}, {"day": {"$lte": "2026-10-05"}}], "likely_bot": false}
