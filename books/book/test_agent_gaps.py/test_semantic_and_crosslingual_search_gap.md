# current text-match search over the (English) documents

  [English, direct        ] 'ideal customer profile'
      -> 2 hits: ['Ideal customer profile', 'Q3 content calendar']
  [French, same intent     ] 'quels prospects contacter'
      -> 0 hits: []
  [Paraphrase (retention)  ] 'reducing churn and keeping customers'
      -> 6 hits: ['Ideal customer profile', 'Genco account plan', 'Q3 content calendar', 'Predictive database positioning', 'R&D roadmap themes', 'Daily note — Genco pilot kickoff']
  [Synonym (GTM)           ] 'go-to-market plan'
      -> 2 hits: ['Genco account plan', 'Onboarding runbook']

# the gap, made concrete

a clear French intent returns 0 results (semantics lost in translation)
a paraphrase returns 6 of 7 docs (token overlap on common words, no relevance)
