# assign a lead, a deal, and a task to the SDR

sdr my_work: 3 items (contacts 1, deals 1, todos 1)

# reassign the lead to the operator, unassign the deal

sdr now: 1 (the task)
operator now: 1 (the lead)
assignment map (entity -> owner):
  contacts -> u_operator
  todos -> u_sdr

# the CRM tables are untouched by assignment (join table only)

contacts still: 50, deals: 80, todos: 102
