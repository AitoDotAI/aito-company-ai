# the default return is a receipt

keys:   ['rev', 'status', 'todo_id']
status: ready  rev set: True
carries the detail: False

# but the write landed in full

append is on the stored row:  True
earlier detail still present: True
stored detail is 8k chars; receipt is 84 chars

# rev proves which version it landed on

rev advanced: True

# return_detail=True opts back into the full row

carries the detail: True
and the title too:  True

# a write that does not persist raises rather than returning a receipt

TodoWriteNotPersisted raised: a receipt always means persisted
