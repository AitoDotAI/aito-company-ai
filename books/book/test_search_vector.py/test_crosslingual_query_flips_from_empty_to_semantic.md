# index built, with embeddings

indexed 353 items; vectors 353

# a French query over English documents: 'quels prospects contacter au sujet des prix'

  _query request:  {'from': 'search_items', 'where': {'$and': [{'kind': 'doc'}, {'$or': [{'content': {'$match': 'quels'}}, {'content': {'$match': 'prospects'}}, {'content': {'$match': 'contacter'}}, {'content': {'$match': 'au'}}, {'content': {'$match': 'sujet'}}, {'content': {'$match': 'des'}}, {'content': {'$match': 'prix'}}]}]}, 'orderBy': {'$similarity': {'content': 'quels prospects contacter au sujet des prix'}}, 'limit': 10, 'select': ['kind', 'source_id', 'title']}
  _query returned: 0 hits
  _query request:  {'from': 'search_items', 'where': {'$and': [{'kind': 'doc'}, {'$or': [{'content': {'$match': 'quels'}}, {'content': {'$match': 'prospects'}}, {'content': {'$match': 'contacter'}}, {'content': {'$match': 'au'}}, {'content': {'$match': 'sujet'}}, {'content': {'$match': 'des'}}, {'content': {'$match': 'prix'}}]}]}, 'orderBy': {'$similarity': {'content': 'quels prospects contacter au sujet des prix'}}, 'limit': 50, 'select': ['kind', 'source_id', 'title']}
  _query request:  {'$nearest': 'search_vectors'}

text-match ($match):   0 hits  []
blended (+ $nearest):  semantic=True, top 5:
   [doc] Nakatomi OÜ — account plan
   [doc] Genco account plan
   [doc] Daily note — Genco pilot kickoff
   [doc] Pymt Oy — renewal risk
   [doc] Ideal customer profile

# an English exact query keeps its exact match (interleave, not vector-only)

'pricing' -> ['Nakatomi OÜ — account plan', 'What we learned losing ERP deals', 'Daily note — Genco pilot kickoff', 'Genco account plan', 'Mooby Ab — technical evaluation']
