# unset: reads use the real clock

reckoning: None
today() is the real date: True
a live instance cannot drift into a fake date by accident

# set: reads reckon from that date

reckoning: 2026-06-12
today():   2026-06-12
differs from the real clock: True
