# no table populated yet → the roster falls back to board.toml

default (from board.toml): ['gtm', 'marketing', 'product', 'learning', 'chair']

# seed the roster into Aito; it reads back from the table

seeded 5; from Aito: ['gtm', 'marketing', 'product', 'learning', 'chair']

# add an advisor (the write MCP + the dashboard both make)

after add: ['gtm', 'marketing', 'product', 'learning', 'chair', 'finance']
finance persona: Bill Gurley

# retune its reads, then remove it

finance reads: ['deal_pipeline', 'funnel']
remove: {'removed': 'finance', 'remaining': 5}
after remove: ['gtm', 'marketing', 'product', 'learning', 'chair']

# guards: an unknown read and a duplicate id raise (rule 3)

unknown read -> unknown read(s) ['crystal_ball']; have ['deal_pipeline', 'decision_scorecard', 'experiment_board', 'funnel', 'last_week', 'recent_changes', 'score_post', 'segment_360', 'todos_area', 'todos_now', 'what_changed', 'who_to_call']
duplicate id -> advisor_id 'gtm' already exists
