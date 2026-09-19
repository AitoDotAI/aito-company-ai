# record a candidate → go → attended(worthwhile)

candidate: status=candidate decided=None outcome=None
go: status=go decided_set=True
attended: status=attended outcome=worthwhile

# an outcome on a non-attended event is refused (rule 3)

an outcome is only graded on an attended event

# unknown event id raises

unknown event_id 'nope'
