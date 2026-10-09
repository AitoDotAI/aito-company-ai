# the reckoning date is READ-ONLY

log.py calls clock.today(): False
log.py still stamps from date.today(): True
todos: reads reckon from clock = True
deals: reads reckon from clock = True
queries: reads reckon from clock = True
routines: reads reckon from clock = True
board: reads reckon from clock = True
