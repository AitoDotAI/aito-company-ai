# ledger(company=<replica>, kind=attribute)

  sfa016 attribute/infra: 'Runs on Azure, in their own subscription'
      source call:call-seed-0511 (external), status: unconfirmed
  sfa014 attribute/billing_model: 'They bill on milestones, not seats'
      source doc:sdc009 (linked), status: active
  sfa013 attribute/procurement: 'Procurement starts once the evaluation convinces them'
      source doc:sdc009 (linked), status: active
  sfa012 attribute/budget_cycle: 'Budget cycle resets in Q1'
      source doc:sdc009 (linked), status: active
  requests: ['facts', 'documents', 'touches', 'changelog']

# ledger(company=<replica>, status=superseded)

  sfa011 decision: 'Decision expected from the founder'
      source call:call-seed-1001 (external), status: superseded
  requests: ['facts', 'documents', 'touches', 'changelog']
  {'kind': 'rumour'} -> refused: unknown kind 'rumour'; known ['attribute', 'commitment', 'contact_info', 'decision', 'derived', 'hold', 'open_question', 'role']
  {'status': 'stale'} -> refused: unknown status 'stale'; known ['active', 'unconfirmed', 'superseded', 'review: source missing', 'review: source changed', 'derived']
  {'slot': 'favourite_colour'} -> refused: unknown slot 'favourite_colour'; known ['billing_model', 'budget_cycle', 'champion', 'customer_status', 'data_model', 'decision_owner', 'deployment', 'headcount', 'infra', 'load', 'other', 'ours', 'pain', 'procurement', 'signer', 'sponsor', 'stack', 'theirs', 'tooling', 'volume']
