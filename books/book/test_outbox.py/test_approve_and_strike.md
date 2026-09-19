# The operator approves one and strikes the other (the ai.i path)

approved: status=approved updated>created=True
struck:   status=struck

# The decision is visible to the next read (the _modify flush, docs/24 bug 5)

statuses now: ['approved', 'struck']
staged remaining: 0

# A row that is no longer staged is not re-decided

outbox <outbox_id> is approved, not staged — only a staged message can be approved or struck
