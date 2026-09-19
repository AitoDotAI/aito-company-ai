# Simulate an old instance: drop the derived `won` column

`won` present after drop: False
rows preserved through the drop: 80

# create_schema re-adds the missing column IN PLACE, no reload

created tables: none
added columns:  {'deals': ['won']}
`won` present again: True; rows unchanged: 80
note: re-added column reads null on existing rows until reloaded
