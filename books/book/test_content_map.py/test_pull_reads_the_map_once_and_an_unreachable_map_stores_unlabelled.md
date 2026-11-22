# Two days, one map read

  map reads: 1; days: ['2026-10-05', '2026-10-06', 'retention', 'web_visitors']

# An unreachable map: the days are stored unlabelled, the run fails

  content_map: content map https://aito.ai/content-map.json: HTTP 503; the days are stored unlabelled, run apply-content-map once it is back
  2026-10-05: sessions 5
  2026-10-06: sessions 0
  problems: ['content_map: content map https://aito.ai/content-map.json: HTTP 503; the days are stored unlabelled, run apply-content-map once it is back']

# A malformed map raises, before any day is stored

  content map: version 2, expected 1
