# Two days, one map read

  map reads: 1; days: ['2026-10-05', '2026-10-06', 'retention', 'web_visitors']

# A map that can't be read fails every day, and nothing is stored

  2026-10-05: content map: AssertionError: content map https://aito.ai/content-map.json: HTTP 503
  2026-10-06: content map: AssertionError: content map https://aito.ai/content-map.json: HTTP 503
