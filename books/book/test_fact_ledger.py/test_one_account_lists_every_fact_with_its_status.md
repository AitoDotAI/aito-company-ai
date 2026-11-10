# ledger(company=<replica>)

  sfa010 contact_info: 'Reach the partner through the office line'
      source call:call-seed-0304 (external), status: active
  sfa009 contact_info: "The partner's work address bounced"
      source mail:mail-seed-0303 (external), status: active
  sfa008 commitment/ours: 'Pricing proposal for the pilot'
      source doc:sdc009 (linked), status: active
  sfa007 commitment/ours: 'Send the pilot scope'
      source mail:mail-seed-0211 (external), status: active
  sfa003 decision: 'The plugin decision mail went to the commercial lead'
      source mail:mail-seed-0211 (external), status: active
  sfa002 role/decision_owner: 'Sponsor says she decides what is sold'
      source call:call-seed-0111 (external), status: active
  sfa014 attribute/billing_model: 'They bill on milestones, not seats'
      source doc:sdc009 (linked), status: active
  sfa013 attribute/procurement: 'Procurement starts once the evaluation convinces them'
      source doc:sdc009 (linked), status: active
  sfa012 attribute/budget_cycle: 'Budget cycle resets in Q1'
      source doc:sdc009 (linked), status: active
  sfa001 role/decision_owner: 'Commercial lead owns the commercial track from the 26.10 split'
      source doc:sdc009 (linked), status: active
  sfa006 role/champion: 'Head of Finance backs the pilot too'
      source touch:st067 (linked), status: active
  sfa005 role/champion: 'Head of Product champions the pilot'
      source call:call-seed-0910 (external), status: active
  sfa004 open_question/theirs: 'Champion asked whether to buy the plugin or publish it themselves'
      source call:call-seed-0910 (external), status: active
  sfa011 decision: 'Decision expected from the founder'
      source call:call-seed-1001 (external), status: superseded
  derived-customer-nakatomi-o derived/customer_status: 'No won deal on record (direct deals only; indirect relationships are not shown yet)'
      source derived: (derived), status: derived
  requests: ['facts', 'documents', 'touches', 'changelog', 'deals', 'companies']
