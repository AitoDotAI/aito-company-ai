# assistant: fetch_page reads a page, its text is fed back, answer cites it

url fetched: ['https://northwind.example.com/pricing']
reply: Northwind lists pricing from €49/user/month.
trace: [{'tool': 'fetch_page', 'args': {'url': 'https://northwind.example.com/pricing'}, 'ok': True}]
grounding: page title='Northwind — Pricing' text='Plans start at €49 per user per month.'
system mentions fetch_page: True
