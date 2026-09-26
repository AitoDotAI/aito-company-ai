# Before: weighted pipeline and the top deal

weighted=765875 open=40
top: se024 Vandelay Oy negotiation w=42000

# Close the top deal as won

{"deal_id": "se024", "stage": "closed_won", "won": true}

# After: the won deal has left the open pipeline

weighted=723875 open=39
confirmed: se024 left the open pipeline, open 40 -> 39
