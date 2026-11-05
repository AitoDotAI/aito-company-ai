# Everything, documents included

  nodes: {'company': 34, 'contact': 60, 'deal': 280, 'document': 7}
  edges: {'about': 7, 'deal_with': 280, 'mentions': 7, 'works_at': 60}
  facets: {'industry': 6, 'relationship': 4, 'country': 5}
  documents with no company: 6, links dropped: 0

# Only customers: the filter crosses the link

  nodes: {'company': 24, 'contact': 42, 'deal': 230}
  companies: where {'relationship': 'customer'}
  companies: where None
  contacts: where {'company_id.relationship': 'customer'}
  deals: where {'company_id.relationship': 'customer'}

# A search: the matches and their neighbourhood

  query 'acme': matched ['company:acme-o']
  nodes: {'company': 1, 'contact': 1, 'deal': 9}
