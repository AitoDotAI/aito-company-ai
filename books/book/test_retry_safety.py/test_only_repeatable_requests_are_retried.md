# A _modify update after one 502

attempts: 2 -> succeeded

# A batch insert after one 502

attempts: 1 -> raised: POST /api/v2/data/t/batch -> 502: Bad Gateway
