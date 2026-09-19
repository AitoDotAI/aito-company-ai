# R&D entering review needs the block

  no block at all    -> REJECTED: status='review' needs a === HANDOFF === block at the end of `detail` (fields: CLAIM:, VERIFY:, SCOPE:, RISK:, PUSHED:)
  header only        -> REJECTED: the === HANDOFF === block is missing VERIFY:, SCOPE:, RISK:, PUSHED:
  missing RISK       -> REJECTED: the === HANDOFF === block is missing RISK:
  complete block     -> accepted

# Every other transition is untouched

  rnd -> ready       -> accepted
  rnd -> done        -> accepted
  rnd -> blocked     -> accepted

# Only R&D — review elsewhere is not the agent-lane handoff

  sales -> review    -> accepted
  operations->review -> accepted
