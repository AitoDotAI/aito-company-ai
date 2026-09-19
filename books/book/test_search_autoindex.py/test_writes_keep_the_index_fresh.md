# A new contact is searchable immediately — no reindex

search 'Zyxwq': ['Zyxwq Vartiainen · Zyxwq Oy']

# A new deal is searchable immediately

search 'Qwptx': ['Qwptx Ltd — pilot']

# A journal entry appears, then drops out when deleted

after add, search 'Jklmn': ['Jklmn breakthrough']
after delete, search 'Jklmn': []
