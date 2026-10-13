# The follow-up step fails after the insert

touch <touch_id> IS recorded; a follow-up step failed (AitoError: POST /api/v2/data/_modify -> 502: Bad Gateway). Do not write it again: a retry returns the existing row.

# The agent retries

already_recorded: True
touches: 150 before, 151 after

# A different engagement is still recorded

already_recorded: None; touches: 152
