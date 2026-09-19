# A Sales todo without a due_date raises (lens invariant)

unexpected columns ['action_type', 'slipped', 'slot', 'stakeholder_id']; offending row: {'todo_id': 'x1', 'area': 'sales', 'title': 'call', 'detail': '', 'status': 'ready', 'priority': '1', 'due_date': '', 'window': '', 'linked_id': '', 'linked_type': 'contact', 'prep_status': 'ready'}

# An Operations todo WITH a due_date raises

unexpected columns ['action_type', 'slipped', 'slot', 'stakeholder_id']; offending row: {'todo_id': 'x1', 'area': 'operations', 'title': 'call', 'detail': '', 'status': 'ready', 'priority': '1', 'due_date': '2026-06-20', 'window': '', 'linked_id': '', 'linked_type': 'instance', 'prep_status': 'ready'}
