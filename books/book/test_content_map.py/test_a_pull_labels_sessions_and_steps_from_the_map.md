# The run report counts the unmapped pages of human visits

  unmapped_pages: {'/docs/api/v2/quickstart/': 1, '/signup/': 1}

# Sessions

  Finland: /blog/every-screen-a-decision/ /pricing/ /signup/
    items=post:every-screen-a-decision site:pricing, categories=None, subcategories=None, verticals=None, domains=None, unmapped_pages=1
  Germany: / ecommerce.aito.ai/cart
    items=site:home cart-recommendations bought-together, categories=mixed, subcategories=None, verticals=E-commerce, domains=ecommerce, unmapped_pages=0
  Netherlands: /wp-login.php
    items=None, categories=None, subcategories=None, verticals=None, domains=None, unmapped_pages=1
  Sweden: /docs/ /docs/api/v2/quickstart/ /docs/
    items=site:docs, categories=None, subcategories=None, verticals=None, domains=None, unmapped_pages=1
  United States: /
    items=site:home, categories=None, subcategories=None, verticals=None, domains=None, unmapped_pages=0

# Steps: a page step carries its page's labels, an event step none

  n=0 page:/                           items=site:home verticals=None
  n=1 demo_signup_cta_clicked          items=None verticals=None
  n=2 page:ecommerce.aito.ai/cart      items=cart-recommendations bought-together verticals=E-commerce
  n=3 instance_create                  items=None verticals=None

# Pooled counts are one _relate

  categories=mixed: 1 visits, rate 1.0
  domains=ecommerce: 1 visits, rate 1.0
  items=bought-together: 1 visits, rate 1.0
  items=cart-recommendations: 1 visits, rate 1.0
  verticals=E-commerce: 1 visits, rate 1.0
  items=site:home: 2 visits, rate 0.5
  items=post:every-screen-a-decision: 1 visits, rate 0.0
  items=site:docs: 1 visits, rate 0.0
  items=site:pricing: 1 visits, rate 0.0
