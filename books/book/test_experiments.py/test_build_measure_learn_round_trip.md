# Build: start a running experiment

id prefix=ex status=running validated=None result=None

# Learn: resolve it to a verdict

status=validated result=0.49 validated=True decided set=True

# a result without a terminal verdict is refused

a result needs a terminal verdict (validated/invalidated/inconclusive), got 'running'
