# A fact sourced from another account's note

  drawn: ['company_id', 'foreign', 'id', 'kind', 'label', 'noted_on']
  counts: {'company': 1, 'contact': 5, 'deal': 1, 'document': 1, 'touch': 16, 'fact': 11}, foreign sources: {'document': 1}
  document reads select: [['doc_id', 'title', 'noted_on', 'company_id', 'stakeholder_id'], ['doc_id', 'title', 'noted_on', 'company_id', 'stakeholder_id']]
  every request listed: ['companies', 'contacts', 'deals', 'documents', 'touches', 'GET /api/v2/schema', 'facts', 'documents', 'touches']

# kinds is respected: no notes asked for, none drawn as sources

  counts: {'company': 1, 'fact': 11}, said_in edges: 0
