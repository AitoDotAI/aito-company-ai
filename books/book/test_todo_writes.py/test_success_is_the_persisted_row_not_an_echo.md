# the engine accepts the write but applies nothing

TodoWriteNotPersisted: td-1: the persisted row differs (want, have): {'detail': ('a 10 KB handoff', None), 'rev': ('rv-<new>', 'rv-0')}
row unchanged: True

# a read that lags the write: retried, then the persisted row returned

returned priority=1 rev set=True
