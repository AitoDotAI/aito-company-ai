# Serve, click the third hit, then mark the first used and the second wrong

  served 5 hits
  after the click the clicked hit leads: True
  impressions for the context: 5 shown + 1 click (none appended by marks)
  the context records the account
  next serve, same order as the click-only baseline: True

# Refused marks

  an item not shown: no impression for context 'ctx_<new>' + item 'doc:nope'
  an unknown context: no impression for context 'ctx_nope' + item 'fact:sfa007'
  a mark that isn't a bool: used must be true or false, got 'yes'
  no mark at all: mark used or flagged_wrong
