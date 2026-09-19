# A new contact is searchable immediately — the write refreshes the view

search 'Zyxwq': ['Zyxwq Vartiainen']

# A new deal is searchable immediately

search 'Qwptx': ['Qwptx Ltd']

# A document appears, then drops out when deleted

after add, search 'Jklmn': ['Jklmn breakthrough']
after delete, search 'Jklmn': []
