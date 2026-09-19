# the multi-hop that used to need a hand-written 3-read join

stalled deals: 15 at 14 companies
contacts at those companies (hand-joined across 3 reads): 14
  e.g. [('Zara Snow', 'Soylent Oy'), ('Hank Brooks', 'Oscorp OÜ'), ('Olivia Marsh', 'Pierce Oy')]

# now: the relationship is a link, so Aito traverses it in one query

contacts.company    (display string): {'type': 'String'}
contacts.company_id (the entity link): {'type': 'String', 'link': 'companies.company_id'}
deals.company_id    (the entity link): {'type': 'String', 'link': 'companies.company_id'}
who_to_reach() traverses company_id in one pass: 14 stalled companies, 14 contacts reached
→ the same answer the hand-join produced, now a single relational query.
