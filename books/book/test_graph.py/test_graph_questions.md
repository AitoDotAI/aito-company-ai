# Each question is one Aito query — request, then what came back

  7/7 queries answered; failed: none

## Who actually pays us, and how much?

  request:  {'from': 'companies', 'where': {'relationship': 'customer'}, 'orderBy': {'$desc': 'mrr_eur'}, 'select': ['name', 'industry', 'country', 'mrr_eur'], 'limit': 6}
  total:    13
    {'country': 'Estonia', 'industry': 'analytics', 'mrr_eur': 13333, 'name': 'Lacuna OÜ'}
    {'country': 'Finland', 'industry': 'consultancy', 'mrr_eur': 10000, 'name': 'Globex Oy'}
    {'country': 'Sweden', 'industry': 'ecommerce', 'mrr_eur': 9583, 'name': 'Gringotts Ab'}

## Who are the people at accounts that pay us?

  request:  {'from': 'contacts', 'where': {'company_id.relationship': 'customer'}, 'select': ['name', 'role', 'company'], 'limit': 6}
  total:    13
    {'company': 'Cobalt Oy', 'name': 'Trent Lake', 'role': 'IT Manager'}
    {'company': 'Hanso Oy', 'name': 'Mallory Vale', 'role': 'Finance Manager'}
    {'company': 'Aperture Oy', 'name': 'Victor Hill', 'role': 'CFO'}

## Which CFOs work at accounts we are still selling to?

  request:  {'from': 'contacts', 'where': {'role': 'CFO', 'company_id.relationship': 'prospect'}, 'select': ['name', 'company', 'country'], 'limit': 6}
  total:    1
    {'company': 'Mooby Ab', 'country': 'Sweden', 'name': 'Quinn Stone'}

## Which accounts have a CTO on file?

  request:  {'from': 'companies', 'where': {'$refs.contacts.company_id': {'$exists': {'role': 'CTO'}}}, 'select': ['name', 'industry', 'relationship'], 'limit': 6}
  total:    6
    {'industry': 'other', 'name': 'Duff BV', 'relationship': 'lost'}
    {'industry': 'accounting', 'name': 'Hardman Oy', 'relationship': 'none'}
    {'industry': 'analytics', 'name': 'Lacuna OÜ', 'relationship': 'customer'}

## What is in play across the accounting industry?

  request:  {'from': 'deals', 'where': {'company_id.industry': 'accounting'}, 'orderBy': {'$desc': 'value_eur'}, 'select': ['company', 'stage', 'value_eur'], 'limit': 6}
  total:    20
    {'company': 'Wayne GmbH', 'stage': 'demo', 'value_eur': 80000}
    {'company': 'Cobalt Oy', 'stage': 'closed_lost', 'value_eur': 80000}
    {'company': 'Cobalt Oy', 'stage': 'closed_lost', 'value_eur': 80000}

## Which accounts have we opened the most deals with?

  request:  {'from': 'companies', 'select': ['name', 'relationship', 'mrr_eur', {'deal_count': {'$length': '$refs.deals.company_id.stage'}}], 'orderBy': {'$desc': 'deal_count'}, 'limit': 6}
  total:    50
    {'deal_count': 5, 'mrr_eur': 0, 'name': 'Abstergo Oy', 'relationship': 'lost'}
    {'deal_count': 5, 'mrr_eur': 13333, 'name': 'Lacuna OÜ', 'relationship': 'customer'}
    {'deal_count': 4, 'mrr_eur': 9583, 'name': 'Gringotts Ab', 'relationship': 'customer'}

## In accounting, how likely is a deal to be won?

  request:  {'from': 'deals', 'where': {'company_id.industry': 'accounting'}, 'predict': 'won', 'select': ['$value', '$p']}
  total:    2
    {'$p': 0.7261508779303686, '$value': False}
    {'$p': 0.27384912206963136, '$value': True}
