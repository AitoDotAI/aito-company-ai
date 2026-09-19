# Surprising data raises, never skips (CLAUDE.md rule 3)

unknown segment:
  unknown segment 'blockchain'; offending row: {'contact_id': 'sc001', 'name': 'Carol Lane', 'company': 'Genco Oy', 'role': 'Partner', 'phone_present': 'false', 'email_present': 'false', 'segment': 'blockchain', 'tier': 'A', 'ai_lifecycle': 'none', 'source': 'cold', 'country': 'Finland', 'notes_tags': 'met-at-event;spreadsheet-heavy', 'created': '2025-07-14'}
missing tier:
  tier is empty; offending row: {'contact_id': 'sc001', 'name': 'Carol Lane', 'company': 'Genco Oy', 'role': 'Partner', 'phone_present': 'false', 'email_present': 'false', 'segment': 'consultancy', 'tier': '', 'ai_lifecycle': 'none', 'source': 'cold', 'country': 'Finland', 'notes_tags': 'met-at-event;spreadsheet-heavy', 'created': '2025-07-14'}
non-boolean phone_present:
  phone_present must be 'true' or 'false', got 'yes'; offending row: {'contact_id': 'sc001', 'name': 'Carol Lane', 'company': 'Genco Oy', 'role': 'Partner', 'phone_present': 'yes', 'email_present': 'false', 'segment': 'consultancy', 'tier': 'A', 'ai_lifecycle': 'none', 'source': 'cold', 'country': 'Finland', 'notes_tags': 'met-at-event;spreadsheet-heavy', 'created': '2025-07-14'}
unknown outcome:
  unknown outcome 'ghosted'; offending row: {'touch_id': 'st101', 'contact_id': 'sc010', 'ts': '2026-04-03T08:49:00', 'weekday': 'fri', 'window': '0800', 'channel': 'call', 'outcome': 'ghosted', 'next_action': '', 'next_action_due': '', 'notes': ''}
weekday contradicts ts:
  weekday 'sun' does not match ts (fri); offending row: {'touch_id': 'st101', 'contact_id': 'sc010', 'ts': '2026-04-03T08:49:00', 'weekday': 'sun', 'window': '0800', 'channel': 'call', 'outcome': 'no_answer', 'next_action': '', 'next_action_due': '', 'notes': ''}
unknown contact:
  unknown contact_id 'nobody'; offending row: {'touch_id': 'st101', 'contact_id': 'nobody', 'ts': '2026-04-03T08:49:00', 'weekday': 'fri', 'window': '0800', 'channel': 'call', 'outcome': 'no_answer', 'next_action': '', 'next_action_due': '', 'notes': ''}
