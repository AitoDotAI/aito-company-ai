# a write to an unversioned row refuses (no unconditional init on the fly)

TodoNotVersioned, names the command: True

# migrate_todo_revs versions every row, each with its own rev

report: {'todos': 3, 'versioned': 3}
all versioned: True  unique: True
re-run is a no-op: {'todos': 3, 'versioned': 0}
now writable: priority=1
