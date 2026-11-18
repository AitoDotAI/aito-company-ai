# add_fact takes no confirmed_by: a caller can't certify its own fact

  confirmed_by among add_fact's parameters: False

# confirm_fact records who and when

  confirmed_by alex@example.com, confirmed_at set: True
  change-log rows: 1

# Refused, naming the fact

  twice: fa-new is already confirmed by alex@example.com at <at>
  unknown id: unknown fact_id 'fa-none'
  no confirmer: no confirmer for sfa016: confirm_fact needs the operator
