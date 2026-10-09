# 33 — Public demo mode (`COMPANY_AI_PUBLIC_DEMO`)

The Company AI can be shown to anonymous visitors on a public host, as the `company`
demo in aito-demo-server. The full plan is in aito-demo-server's
`docs/company-ai-public-demo.md`: the container, the data, the views, the LLM, and the
hazards of the shared demos container. This page is the app's half of the contract.

## What the flag does

`COMPANY_AI_PUBLIC_DEMO=1` makes the app safe to put in front of strangers:

| | |
|---|---|
| **No writes** | every non-GET `/api/*` returns `403 {"error": "read-only public demo…", "public_demo": true}`. The assistant (`POST /api/assistant/chat`) is the one exception, since it only reads. The runtime key should also be the database's READ-ONLY key, so the database refuses writes too |
| **No write side effects on reads** | `/api/search` serves the prebuilt index and logs no impressions. `/api/chats` lists nothing and creates nothing. Chats are global, so one visitor must not see another's |
| **Not the internal instance** | `create_app` refuses to start if `AITO_INSTANCE_URL`'s host is in `PUBLIC_DEMO_DENIED_HOSTS` (`internal.aito.ai`) |
| **No billable or outbound features** | config forces the LLM, embeddings, web search/fetch and MCP **off**, whatever the environment carries. Clearing env vars can't do this: `_env_first` skips empty values, and the unified demos container gives every program every secret, including another demo's OpenAI key. `COMPANY_AI_PUBLIC_DEMO_LLM=1` turns the LLM back on deliberately |
| **The UI knows** | `/api/me` returns `public_demo: true`. The frontend shows a "Public demo — read-only" banner and offers nothing that can only fail: no ＋ Note, no add rows, and no My work, Data or Admin, nor the Posts tab — those read operator-only routes, which stay operator-only on purpose (they expose whole tables, and a demo pointed at the wrong database must not publish them) |
| **A working week** | A public demo serves the shipped seed and runs in a container, with no `./do seed` to record its date — so it reckons from the seed's own anchor (`data/seed/AS_OF`) and says so in the banner. `COMPANY_AI_AS_OF` still overrides it |

A missing or failing model (no key, a non-200, a connection error or a timeout, as in the
Azure OpenAI Sweden Central outage of 2026-09-29) is `503 {"error": <message>,
"llm_unavailable": true}`, not a 500. That's in every mode, not only the demo. The
predictions on the other views never depend on the model.

## Operating it

- **Load the demo database once**, with its read-write key: `create-schema`,
  `load-all --dir data/seed`, `reindex-search`. The runtime then gets only the read-only key.
- **Measured locally:** 58–59 MB RSS in demo mode, idle and under a pass over every view.
- **Done since the plan was written:** the fixed "today" (the seed's anchor, see above),
  the guest UI (banner; My work, Data, Admin and the Posts tab hidden; no write controls),
  and the "weighted pipeline" label (it says it is the operator's own probability).
- **Open by choice:** the Posts board stays hidden rather than readable. Opening the raw
  tables to visitors is safe only while the demo can point at nothing but synthetic data,
  and the host check refuses one known instance, not every real one.

Tests: `book/test_public_demo.py`, offline. It covers the internal-host refusal, eight
write routes refused, reads without side effects, the no-model 503, inherited keys
staying off, and the seed's working week. `frontend/src/publicdemo.test.jsx` covers the
hidden tabs and the missing add row.
