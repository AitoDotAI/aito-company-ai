# The run: no consultative event is new any more

  new_event_types: {}

# Sessions

  Finland: interests=ai tech, domain=erp, stage=building, intro_reached=submit, intro_skipped=False
  Germany: interests=None, domain=None, stage=None, intro_reached=None, intro_skipped=None
  Norway: interests=None, domain=None, stage=None, intro_reached=shown, intro_skipped=False
  Sweden: interests=None, domain=None, stage=None, intro_reached=domain, intro_skipped=True

# The steps stay in `events`, as names

  Finland: page:/ consultative_health consultative_intro_shown consultative_intro_interest consultative_intro_interest consultative_intro_domain consultative_intro_submit consultative_stage page:/pricing/

# The visitor's sentence is nowhere

  found: []

# A profile is a segment: one _relate

  domain=erp: 1 visits, rate 1.0, thin True
  interests=ai: 1 visits, rate 1.0, thin True
  interests=tech: 1 visits, rate 1.0, thin True
  intro_reached=submit: 1 visits, rate 1.0, thin True
  stage=building: 1 visits, rate 1.0, thin True
  intro_skipped=False: 2 visits, rate 0.5, thin True
  intro_reached=domain: 1 visits, rate 0.0, thin True
  intro_reached=shown: 1 visits, rate 0.0, thin True
  intro_skipped=True: 1 visits, rate 0.0, thin True
