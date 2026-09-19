# an unmapped authenticated identity is a guest, not the operator

/api/me role: guest
  add a user             unmapped=403 (403)
  create a token         unmapped=403 (403)
  list tokens            unmapped=403 (403)
  read a raw data sheet  unmapped=403 (403)

# the tokens table is never viewable as a raw sheet, even for the operator

  GET /api/table?name=tokens (operator): 500 (not 200)
