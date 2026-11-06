# Steps on the fixture day

  11 steps, runs 1
  n=0 page:/                           kpi=None after_sandbox=True exit=False
  n=1 demo_signup_cta_clicked          kpi=None after_sandbox=True exit=False
  n=2 page:ecommerce.aito.ai/cart      kpi=None after_sandbox=True exit=False
  n=3 instance_create                  kpi=sandbox after_sandbox=False exit=True

# The graph walks: two hops back from the sandbox step

  1

# The arrival is on every step

  steps with a post platform: ['linkedin'], 3 steps

# Forgetting a visitor removes its steps

  steps left: 0
