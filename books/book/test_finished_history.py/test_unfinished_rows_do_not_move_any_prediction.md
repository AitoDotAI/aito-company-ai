# Predictions on the seed

  deals p_win none/True: (0.5811174732355558, 'profile')
  deals p_win consultant_lock/False: (0.1474704339552225, 'profile')
  posts p_win linkedin/story: 0.07708593337238505
  posts base_p_win linkedin: 0.07708593337238505
  posts lever tone: [('narrate', 0.1437361928193007), ('builder', 0.020445965105673314), ('explainer', 0.017134426400555357), ('announce', 0.015253552366722038)]
  posts lever link_placement: [('comment', 0.14726284053964678), ('body', 0.010253485439382573)]
  posts lever ai_made: [('ai-assisted', 0.15645666481156598), ('manual', 0.07128962592598592), ('ai', 0.016141645851069177)]
  todos slip sales/high/prep_needed: 0.5429406344385403
  experiments aito_p small: 0.6917712120779695
  experiments aito_p medium: 0.411178752675413
  experiments aito_p large: 0.36568494429534304
  decisions aito_p low: 0.36172120232690613
  decisions aito_p medium: 0.5414084765760955
  decisions aito_p high: 0.6285753659985311
  graph baseline_p: 0.256198347107438
  graph conditioned_p (CTO on file): 0.3571860153023632
  graph explained-odds p: 0.7069165325069414

# Inject unfinished rows whose target reads False

  +40 open deals, won=False
  +22 unmeasured posts, won=False
  +16 open todos, slipped=False
  +15 running experiments, validated=False
  +32 accepted decisions, stale accepted=False

# Predictions that moved (must be none)

  graph conditioned_p (CTO on file): 0.3571860153023632 -> 0.32115428818605835  (known engine leak)
  graph explained-odds p: 0.7069165325069414 -> 0.578246537876114  (known engine leak)
