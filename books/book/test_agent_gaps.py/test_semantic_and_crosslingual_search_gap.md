# current text-match search over the (English) documents

  [English, direct        ] 'ideal customer profile'
      -> 2 hits: ['Ideal customer profile', 'Q3 content calendar']
  [French, same intent     ] 'quels prospects contacter'
      -> 0 hits: []
  [Paraphrase (retention)  ] 'reducing churn and keeping customers'
      -> 10 hits: ['Ideal customer profile', 'Genco account plan', 'Q3 content calendar', 'Nakatomi OÜ — account plan', 'What we learned losing ERP deals', 'Slate OÜ — discovery call', 'Mooby Ab — technical evaluation', 'Predictive database positioning', 'R&D roadmap themes', 'Pymt Oy — renewal risk']
  [Synonym (GTM)           ] 'go-to-market plan'
      -> 7 hits: ['Genco account plan', 'Nakatomi OÜ — account plan', 'Ideal customer profile', 'Daily note — Genco pilot kickoff', 'Nimbus OÜ — quarterly review', 'Pymt Oy — renewal risk', 'What we learned losing ERP deals']

# the gap, made concrete

a clear French intent returns 0 results (semantics lost in translation)
a paraphrase returns 10 of 13 docs (token overlap on common words, no relevance)
