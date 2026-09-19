# save two conversations, list them newest-first

list: [('c-def', 'Marketing ideas', 200), ('c-abc', "How's my pipeline?", 100)]

# get one back, with its messages and a round-tripped tool trace

c-def msgs: [{'role': 'user', 'content': 'ideas?'}, {'role': 'assistant', 'content': 'post more', 'trace': [{'tool': 'score_post', 'ok': True}]}]

# overwrite (replace the conversation), then remove

after edit, newest-first ids: ['c-abc', 'c-def']
remove c-abc: {'removed': 'c-abc', 'deleted': 2}
remaining: ['c-def']
remove missing: {'removed': 'c-nope', 'deleted': 0}

# a bad id is refused — no path traversal, no odd names

  '../evil' -> bad conversation id '../evil'
  'a/b' -> bad conversation id 'a/b'
  'with.dot' -> bad conversation id 'with.dot'
  '' -> bad conversation id ''
