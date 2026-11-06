# A value outside the per-kind vocabulary is refused with the row

  {'kind': 'role', 'slot': 'cheerleader'}: a role fact needs slot in ['champion', 'decision_owner', 'other', 'sponsor'], got 'cheerleader'
  {'kind': 'commitment', 'slot': 'ours'}: a commitment fact needs state in ['drafted', 'sent'], got ''
  {'kind': 'decision', 'slot': 'ours'}: a decision fact takes no slot, got 'ours'
  {'kind': 'gossip'}: unknown kind 'gossip'
  {'kind': 'decision', 'source_kind': 'rumour'}: unknown source_kind 'rumour'
  {'kind': 'contact_info', 'state': 'maybe'}: a contact_info fact needs state in ['bounced', 'current', 'invalid'], got 'maybe'

# A retry inside the window returns the first row

  same fact_id, already_recorded

# Supersede: same company and kind only; the old fact stays, inactive

  sfa001 -> sfa003: sfa001 is a role, sfa003 a decision
  sfa001 -> sfa012: sfa001 is on nakatomi-o, sfa012 on strickland-gmbh
  sfa011 -> sfa003: sfa011 is already superseded by sfa003
  after fact 2 -> fact 1: conflicts []
  list_facts(active_only=False) still has fact 2, superseded by fact 1
