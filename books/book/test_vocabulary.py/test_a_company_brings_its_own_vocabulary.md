# the default vocabulary is this repository's own business

SEGMENTS: ['accounting', 'analytics', 'consultancy', 'ecommerce', 'erp', 'other']

# a consultancy's taxonomy replaces it

SEGMENTS:      ['industry', 'other', 'public-sector', 'retail']
TIERS:         ['growth', 'long-tail', 'strategic']
DEAL_BLOCKERS: ['framework-agreement', 'none', 'procurement']
untouched sets keep their defaults — SOURCES: ['cold', 'referral', 'trigger', 'warm']

# and their rows load, where before they raised

a public-sector contact parses: segment='public-sector'
