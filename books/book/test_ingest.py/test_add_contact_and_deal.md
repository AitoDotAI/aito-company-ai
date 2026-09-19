# Add a contact

contact_id prefix: c
funnel flags start false: [False, False, False, False]
phone_present coerced to bool: True
notes_tags tokenized: 'q3-budget'
queryable immediately: True

# Add a deal — it enters the open pipeline

won derived from stage 'qualified': None
open deals 15 -> 16
new deal ranked with a close-likelihood: p_win=True
