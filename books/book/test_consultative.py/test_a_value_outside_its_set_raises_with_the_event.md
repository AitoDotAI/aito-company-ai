# The fixed sets

  CONSULTATIVE_INTERESTS: ('ai', 'tech', 'usecases')
  CONSULTATIVE_DOMAINS: ('accounting', 'erp', 'ecommerce', 'service', 'agents', 'other')
  CONSULTATIVE_STAGES: ('exploring', 'building', 'need', 'partner')
  INTRO_STEPS: ('shown', 'interest', 'domain', 'skip', 'submit')

# Refused

  a domain: consultative domain 'banking' not in ('accounting', 'erp', 'ecommerce', 'service', 'agents', 'other'): {'$insert_id': 'cons-0006', 'event_type': 'Consultative: 
  an interest: consultative interests 'tech pricing' not in ('ai', 'tech', 'usecases'): {'$insert_id': 'cons-0004', 'event_type': 'Consultative: intro interest', 'event_time':
  a stage: consultative stage 'buying' not in ('exploring', 'building', 'need', 'partner'): {'$insert_id': 'cons-0008', 'event_type': 'Consultative: stage', 'event_time': 
  an intro step: consultative intro step 'opened' not in ('shown', 'interest', 'domain', 'skip', 'submit'): {'$insert_id': 'cons-0003', 'event_type': 'Consultative: intro shown'
