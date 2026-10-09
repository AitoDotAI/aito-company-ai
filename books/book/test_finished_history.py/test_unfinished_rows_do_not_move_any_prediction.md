# Predictions on the seed

  deals p_win none/True: (0.5825362428186927, 'profile')
  deals p_win consultant_lock/False: (0.1474704339552225, 'profile')
  posts p_win linkedin/story: 0.07708593337238505
  posts base_p_win linkedin: 0.07708593337238505
  posts lever tone: [('builder', 0.4162859339643815), ('explainer', 0.37243950320820646), ('announce', 0.3452568124285155), ('narrate', 0.1616384706581851)]
  posts lever link_placement: [('comment', 0.5051749792793649), ('body', 0.06460941047488093)]
  posts lever ai_made: [('ai-assisted', 0.388463248399458), ('ai', 0.1553251905595517), ('manual', 0.06232113985086398)]
  todos slip sales/high/prep_needed: 0.5429733923243041
  experiments aito_p small: 0.6917712120779695
  experiments aito_p medium: 0.411178752675413
  experiments aito_p large: 0.36568494429534304
  decisions aito_p low: 0.36172120232690613
  decisions aito_p medium: 0.5414084765760955
  decisions aito_p high: 0.628575365998531
  graph baseline_p: 0.256198347107438
  graph conditioned_p (CTO on file): 0.3571860153023632
  graph explained-odds p: 0.7076767341934111

# Inject unfinished rows whose target reads False

  +40 open deals, won=False
  +22 unmeasured posts, won=False
  +16 open todos, slipped=False
  +15 running experiments, validated=False
  +32 accepted decisions, stale accepted=False

# Predictions that moved (must be none)

  graph conditioned_p (CTO on file): 0.3571860153023632 -> 0.32115428818605835  (known engine leak)
  graph explained-odds p: 0.7076767341934111 -> 0.5788369146657651  (known engine leak)
