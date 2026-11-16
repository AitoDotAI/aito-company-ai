# Update: the active node is done

  action: updated, request: {"set": {"state": "Finished in the seed.", "status": "done", "updated_on": "2026-11-15"}, "update": "tech_nodes", "where": {"node_id": "e2"}}
  fields that changed: ['state', 'status', 'updated_on']

# Create: a new node that requires two existing ones

  action: created, node: {"branch": "Apps", "doc_id": null, "era": 2, "metric": "not started", "next": "Wait for its prerequisites.", "node_id": "new-line", "owner": "operator", "reasons": null, "recommendation": null, "requires": ["a1", "a2"], "row": 40, "state": "Planned.", "status": "locked", "title": "A new line", "updated_on": "2026-11-15", "what": "Something new."}
