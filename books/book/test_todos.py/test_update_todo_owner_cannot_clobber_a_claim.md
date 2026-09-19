# unowned -> update_todo owner=core-a is a valid first claim

first claim via edit -> owner='core-a'

# owner=core-b over a live holder is refused — no silent steal

core-b edit -> ClaimTaken; names holder=True points at claim_todo=True

# owner=core-a (the same holder) is idempotent

same-owner edit -> owner='core-a'

# owner='' clears the claim — an operator freeing a stuck agent

clear edit -> owner=None
