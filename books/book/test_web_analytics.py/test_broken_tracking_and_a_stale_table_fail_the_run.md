# Run health

a normal day: problems=[] warnings=[]
events but no sessions: tracking renamed: problems=['2026-10-09: 40 events but no sessions: page-view events renamed, or not where the parser looks'] warnings=[]
a quiet day: a warning only: problems=[] warnings=['2026-10-09: no visits pulled']
a day that failed: problems=['2026-10-09: RuntimeError: Amplitude 503'] warnings=[]
the newest stored day is 3 days old: problems=['newest stored day is 2026-10-07, more than 2 days old'] warnings=[]
nothing stored at all: problems=['web_sessions holds no day at all'] warnings=['2026-10-09: no visits pulled']
