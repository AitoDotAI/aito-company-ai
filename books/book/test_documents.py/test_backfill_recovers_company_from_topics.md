# dry run: plans the resolvable doc, writes nothing

resolved=1 ambiguous=1 left_null=9
planned (ours): [('Acme OÜ', 'Backfill target (jnA)')]
doc A company after dry run: None

# apply: the resolvable doc gets company + a resolving company_id link

doc A -> company='Acme OÜ' company_id='acme-o' link='Acme OÜ'

# browsable by account: the by-company feed now finds it

feed(company=name0) includes 'Backfill target (jnA)': True

# ambiguous, untagged, and junk-company-tag notes stay null, not guessed

  ambiguous: company=None
  no-company-tag: company=None
  junk-company-tag: company=None
