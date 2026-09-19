# Before: weighted pipeline and the top deal

weighted=305500 open=15
top: se002 Wayne GmbH demo w=52000

# Close the top deal as won

{"deal_id": "se002", "stage": "closed_won", "won": true}

# After: the won deal has left the open pipeline

weighted=253500 open=14
confirmed: se002 left the open pipeline, open 15 -> 14
