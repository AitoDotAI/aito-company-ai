# session_key

  16 hex: True, equals the bare sha256: False
  changes with the salt: True

# visitor_key: one per browser

  same browser twice: True, two browsers differ: True, equals the bare sha256: False

# Stored rows carry it

  5 rows, every visitor_key 16 hex: True

# No salt, no key

  raised: COMPANY_AI_WEB_SALT is not set: the web keys are salted (docs/36)
