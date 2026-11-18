# The fixture map

  /: {'kind': 'page', 'items': ['site:home'], 'categories': [], 'subcategories': [], 'verticals': [], 'domains': []}
  /pricing/: {'kind': 'page', 'items': ['site:pricing'], 'categories': [], 'subcategories': [], 'verticals': [], 'domains': []}
  /docs/: {'kind': 'page', 'items': ['site:docs'], 'categories': [], 'subcategories': [], 'verticals': [], 'domains': []}
  /blog/every-screen-a-decision/: {'kind': 'post', 'items': ['post:every-screen-a-decision'], 'categories': [], 'subcategories': [], 'verticals': [], 'domains': []}
  ecommerce.aito.ai/cart: {'kind': 'demo', 'items': ['cart-recommendations', 'bought-together'], 'categories': ['mixed'], 'subcategories': [], 'verticals': ['E-commerce'], 'domains': ['ecommerce']}
  /use-cases/invoice-coding/: {'kind': 'usecase', 'items': ['invoice-coding'], 'categories': ['automate'], 'subcategories': ['categorization-routing'], 'verticals': ['ERP', 'Accounting'], 'domains': ['erp', 'accounting']}

# Refused, naming the entry

  an unknown version: content map: version 2, expected 1
  an unknown kind: content map '/x/': kind 'video', expected one of ['demo', 'page', 'post', 'solution', 'usecase']: {'item': 'x', 'kind': 'video'}
  an unknown field: content map '/x/': unknown fields ['tags']: {'item': 'x', 'kind': 'page', 'tags': ['a']}
  no item: content map '/x/': needs exactly one of item and items: {'kind': 'page'}
  a value with a space: content map '/x/': 'Financial services' is not one whitespace-free token: {'item': 'x', 'kind': 'usecase', 'verticals': ['Financial services']}
  a key with a query: content map: bad page key '/x/?a=1': {'item': 'x', 'kind': 'page'}
