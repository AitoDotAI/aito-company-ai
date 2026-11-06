# Strickland GmbH: one hold from antti, no release

  HOLD

# A hold or a release from any other source is refused

  mail: refused: a hold or its release needs source_kind 'antti', got 'mail'
  call: refused: a hold or its release needs source_kind 'antti', got 'call'
  doc: refused: a hold or its release needs source_kind 'antti', got 'doc'
  touch: refused: a hold or its release needs source_kind 'antti', got 'touch'

# A release from antti, superseding the hold, releases this one account

  released

# Unclear holds show HOLD (unclear: reason), never released

  a release that supersedes nothing: HOLD (unclear: a release that supersedes no hold)
  two active holds: HOLD (unclear: two active holds (fa-new, fa-new); a release that supersedes no hold)
  a hold row from mail: HOLD (unclear: two active holds (fa-direct-1, fa-new); a release that supersedes no hold; a hold fact with source mail (fa-direct-1))

# Antti resolves the stray row: his fact supersedes it, and the state is recomputed

  the stray row as the new side: refused: fa-direct-1 has source_kind 'mail'
  after superseding the stray row with Antti's release: released
