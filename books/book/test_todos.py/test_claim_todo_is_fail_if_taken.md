# claim_todo sets owner; a different agent is refused; the owner is idempotent

core-a claim   -> owner=core-a claimed=True
core-b claim   -> ClaimTaken, names the owner: True
core-a re-claim -> already_mine=True
