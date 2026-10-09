# Each question is one Aito query — request, then what came back

  9/9 queries answered; failed: none

## What kind of company is this, judged only by who works there?

  request:  {'from': 'companies', 'where': {'$refs.contacts.company_id': {'$exists': {'role': 'CFO'}}}, 'predict': 'industry', 'select': ['$value', '$p'], 'limit': 5}
  total:    6
    {'$p': 0.45180876109960416, '$value': 'accounting'}
    {'$p': 0.18676738303391519, '$value': 'erp'}
    {'$p': 0.15975007808127015, '$value': 'ecommerce'}

## An accounting account, a champion on board, nothing blocking — what are the odds?

  request:  {'from': 'deals', 'where': {'company_id.industry': 'accounting', 'champion_present': True, 'blocker': 'none'}, 'predict': 'won', 'select': ['$value', '$p', '$why']}
  total:    2
    {'$p': 0.7076767341934111, '$value': True}
    {'$p': 0.2923232658065889, '$value': False}
    why: blocker=none                               x1.75
    why: company_id.industry=accounting             x1.45
    why: champion_present=True                      x1.42

## At an account where we know a CTO, how likely is a deal to close?

  request:  {'from': 'deals', 'where': {'company_id.$refs.contacts.company_id': {'$exists': {'role': 'CTO'}}}, 'predict': 'won', 'select': ['$value', '$p', '$why']}
  total:    2
    {'$p': 0.6428139846976368, '$value': False}
    {'$p': 0.3571860153023632, '$value': True}
    why: company_id.$refs.contacts.company_id has role=CTO x1.38

## Who are the people at accounts that pay us?

  request:  {'from': 'contacts', 'where': {'company_id.relationship': 'customer'}, 'select': ['name', 'role', 'company'], 'limit': 6}
  total:    42
    {'company': 'Genco Oy', 'name': 'Judy Frost', 'role': 'CTO'}
    {'company': 'Onyx Oy', 'name': 'Frank Pike', 'role': 'IT Manager'}
    {'company': 'Dunder GmbH', 'name': 'Quinn Rivers', 'role': 'CTO'}

## Which accounts have a CTO on file?

  request:  {'from': 'companies', 'where': {'$refs.contacts.company_id': {'$exists': {'role': 'CTO'}}}, 'select': ['name', 'industry', 'relationship'], 'limit': 6}
  total:    8
    {'industry': 'accounting', 'name': 'Dunder GmbH', 'relationship': 'customer'}
    {'industry': 'analytics', 'name': 'Genco Oy', 'relationship': 'customer'}
    {'industry': 'other', 'name': 'Prestige Oy', 'relationship': 'customer'}

## Which CFOs work at accounts we are still selling to?

  request:  {'from': 'contacts', 'where': {'role': 'CFO', 'company_id.relationship': 'prospect'}, 'select': ['name', 'company', 'country'], 'limit': 6}
  total:    2
    {'company': 'Initech Oy', 'country': 'Finland', 'name': 'Zara Knight'}
    {'company': 'Pierce Oy', 'country': 'Finland', 'name': 'Frank Stone'}

## What is in play across the accounting industry?

  request:  {'from': 'deals', 'where': {'company_id.industry': 'accounting'}, 'orderBy': {'$desc': 'value_eur'}, 'select': ['company', 'stage', 'value_eur'], 'limit': 6}
  total:    79
    {'company': 'Hanso GmbH', 'stage': 'lead', 'value_eur': 80000}
    {'company': 'Acme OÜ', 'stage': 'closed_won', 'value_eur': 80000}
    {'company': 'Pymt Oy', 'stage': 'closed_won', 'value_eur': 80000}

## Which accounts have we opened the most deals with?

  request:  {'from': 'companies', 'select': ['name', 'relationship', 'mrr_eur', {'deal_count': {'$length': '$refs.deals.company_id.stage'}}], 'orderBy': {'$desc': 'deal_count'}, 'limit': 6}
  total:    34
    {'deal_count': 24, 'mrr_eur': 21250, 'name': 'Delos Ab', 'relationship': 'customer'}
    {'deal_count': 19, 'mrr_eur': 0, 'name': 'Pendant Oy', 'relationship': 'prospect'}
    {'deal_count': 17, 'mrr_eur': 8750, 'name': 'Vertex GmbH', 'relationship': 'customer'}

## How likely is any closed deal to have been won?

  request:  {'from': {'from': 'deals', 'where': {'stage': {'$or': ['closed_lost', 'closed_won']}}}, 'predict': 'won', 'select': ['$value', '$p']}
  total:    2
    {'$p': 0.743801652892562, '$value': False}
    {'$p': 0.256198347107438, '$value': True}
