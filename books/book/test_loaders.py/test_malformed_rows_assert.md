# Surprising data raises, never skips (CLAUDE.md rule 3)

unknown segment:
  unknown segment 'blockchain'; offending row: {'contact_id': 'sc001', 'name': 'Alice Hill', 'company': 'Tyrell Oy', 'role': 'CEO', 'phone_present': 'false', 'email_present': 'true', 'segment': 'blockchain', 'tier': 'A', 'ai_lifecycle': 'operating', 'source': 'trigger', 'country': 'Finland', 'notes_tags': 'founder-led;podcast-listener;rfp-soon', 'created': '2025-08-02'}
missing tier:
  tier is empty; offending row: {'contact_id': 'sc001', 'name': 'Alice Hill', 'company': 'Tyrell Oy', 'role': 'CEO', 'phone_present': 'false', 'email_present': 'true', 'segment': 'erp', 'tier': '', 'ai_lifecycle': 'operating', 'source': 'trigger', 'country': 'Finland', 'notes_tags': 'founder-led;podcast-listener;rfp-soon', 'created': '2025-08-02'}
non-boolean phone_present:
  phone_present must be 'true' or 'false', got 'yes'; offending row: {'contact_id': 'sc001', 'name': 'Alice Hill', 'company': 'Tyrell Oy', 'role': 'CEO', 'phone_present': 'yes', 'email_present': 'true', 'segment': 'erp', 'tier': 'A', 'ai_lifecycle': 'operating', 'source': 'trigger', 'country': 'Finland', 'notes_tags': 'founder-led;podcast-listener;rfp-soon', 'created': '2025-08-02'}
unknown outcome:
  unknown outcome 'ghosted'; offending row: {'touch_id': 'st004', 'contact_id': 'sc029', 'ts': '2026-04-03T12:38:00', 'weekday': 'fri', 'window': '1215', 'channel': 'email', 'outcome': 'ghosted', 'next_action': '', 'next_action_due': '', 'notes': 'replied, lukewarm but open'}
weekday contradicts ts:
  weekday 'sun' does not match ts (fri); offending row: {'touch_id': 'st004', 'contact_id': 'sc029', 'ts': '2026-04-03T12:38:00', 'weekday': 'sun', 'window': '1215', 'channel': 'email', 'outcome': 'reply', 'next_action': '', 'next_action_due': '', 'notes': 'replied, lukewarm but open'}
unknown contact:
  unknown contact_id 'nobody'; offending row: {'touch_id': 'st004', 'contact_id': 'nobody', 'ts': '2026-04-03T12:38:00', 'weekday': 'fri', 'window': '1215', 'channel': 'email', 'outcome': 'reply', 'next_action': '', 'next_action_due': '', 'notes': 'replied, lukewarm but open'}
