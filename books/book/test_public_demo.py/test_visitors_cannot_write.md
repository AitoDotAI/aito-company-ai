# every write is a 403 with a readable reason

  add a todo             POST   /api/todos                   -> 403 read-only public demo: changes are disabled here
  edit a todo            PATCH  /api/todos/td-1              -> 403 read-only public demo: changes are disabled here
  complete a todo        POST   /api/todos/td-1/complete     -> 403 read-only public demo: changes are disabled here
  add a contact          POST   /api/contacts                -> 403 read-only public demo: changes are disabled here
  save a chat            PUT    /api/chats/c1                -> 403 read-only public demo: changes are disabled here
  delete a chat          DELETE /api/chats/c1                -> 403 read-only public demo: changes are disabled here
  record a search click  POST   /api/search/click            -> 403 read-only public demo: changes are disabled here
  run a routine          POST   /api/routines/r1/run         -> 403 read-only public demo: changes are disabled here
