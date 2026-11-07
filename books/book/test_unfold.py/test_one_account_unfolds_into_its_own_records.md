# network(focus=<replica>)

  nodes: {'company': 1, 'contact': 5, 'deal': 1, 'document': 1, 'touch': 16, 'fact': 13}
  edges: {'about': 1, 'concerns': 8, 'deal_with': 1, 'fact_of': 13, 'mentions': 1, 'said_in': 6, 'touched': 16, 'works_at': 5}

## The requests

  companies: where {'company_id': 'nakatomi-o'}
  contacts: where {'company_id': 'nakatomi-o'}
  deals: where {'company_id': 'nakatomi-o'}
  documents: where {'company_id': 'nakatomi-o'}
  touches: where {'contact_id.company_id': 'nakatomi-o'}
  GET /api/v2/schema
  facts: where {'company_id': 'nakatomi-o'}
  documents: where {'doc_id': {'$or': ['sdc009']}}
  touches: where {'touch_id': {'$or': ['call-seed-0111', 'call-seed-0304', 'call-seed-0910', 'st067']}}
  superseded facts left out: ['sfa011']

# Without focus, the graph is unchanged: no touches or facts

  kinds: ['company', 'contact', 'deal']
