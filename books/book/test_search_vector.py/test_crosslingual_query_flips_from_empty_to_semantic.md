# index built, with embeddings

indexed 365 items; vectors 365

# a French query over English documents: 'quels prospects contacter au sujet des prix'

  _query request:  {'from': 'search_items', 'where': {'$and': [{'kind': 'doc'}, {'$or': [{'content': {'$match': 'quels'}}, {'content': {'$match': 'prospects'}}, {'content': {'$match': 'contacter'}}, {'content': {'$match': 'au'}}, {'content': {'$match': 'sujet'}}, {'content': {'$match': 'des'}}, {'content': {'$match': 'prix'}}]}]}, 'orderBy': {'$similarity': {'content': 'quels prospects contacter au sujet des prix'}}, 'limit': 10, 'select': ['kind', 'source_id', 'title']}
  _query returned: 0 hits
  _query request:  {'from': 'search_items', 'where': {'$and': [{'kind': 'doc'}, {'$or': [{'content': {'$match': 'quels'}}, {'content': {'$match': 'prospects'}}, {'content': {'$match': 'contacter'}}, {'content': {'$match': 'au'}}, {'content': {'$match': 'sujet'}}, {'content': {'$match': 'des'}}, {'content': {'$match': 'prix'}}]}]}, 'orderBy': {'$similarity': {'content': 'quels prospects contacter au sujet des prix'}}, 'limit': 50, 'select': ['kind', 'source_id', 'title']}
  _query request:  {'$nearest': 'search_vectors'}

text-match ($match):   0 hits  []
blended (+ $nearest):  semantic=True
top 5 as a set, expected: ['Daily note — Genco pilot kickoff', 'Genco account plan', 'Ideal customer profile', 'Nakatomi OÜ — account plan', 'Pymt Oy — renewal risk']
same set, up to boundary ties within 0.003: True

# an English exact query keeps its exact match (interleave, not vector-only)

text-match's top hit 'Nakatomi OÜ — account plan' leads the blend: True
