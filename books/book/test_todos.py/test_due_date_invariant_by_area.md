# Sales (calendar area) requires a due_date

  no due_date  -> rejected: open sales todo needs a due_date
  with due_date -> accepted

# Operations (deadline area) allows an OPTIONAL due_date

  no due_date   -> accepted
  with due_date -> accepted

# R&D (pipeline area) forbids a due_date

  no due_date   -> accepted
  with due_date -> rejected: open rnd todo must not have a due_date
