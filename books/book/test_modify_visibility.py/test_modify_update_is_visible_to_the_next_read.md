# engine build: 2.11.4

  seeded: r1=before r2=before

# read back immediately, with no intervening write

  r2 over ~4s: ['AFTER', 'AFTER', 'AFTER', 'AFTER', 'AFTER']
  visible without a flush: True

# after an optimize (the flush update_entries performs)

  r2 = AFTER
  r1 untouched = before

# verdict

  docs/24 bug 5 does NOT reproduce on this build — the update is visible to the next read without a flush
