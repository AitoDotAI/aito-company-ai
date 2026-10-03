# a set-but-unparseable value is a configuration error

'yesterday': COMPANY_AI_AS_OF='yesterday' is not an ISO date (YYYY-MM-DD)
'2026-13-01': COMPANY_AI_AS_OF='2026-13-01' is not an ISO date (YYYY-MM-DD)
'12/06/2026': COMPANY_AI_AS_OF='12/06/2026' is not an ISO date (YYYY-MM-DD)

# blank and whitespace mean 'use the real clock'

'': None
'   ': None
