# a first export, problems planted

rolodex.csv          61 rows  64 problem(s)
    unknown segment 'retail'  (31 rows: line 3, 5, 7, 9, 11, 13, 15, 17, … +23 more)
      → allowed: accounting, analytics, consultancy, ecommerce, erp, other — or add it to SEGMENTS in your vocabulary file (COMPANY_AI_VOCABULARY, docs/32)
    unknown segment 'public-sector'  (30 rows: line 2, 4, 6, 8, 10, 12, 14, 16, … +22 more)
      → allowed: accounting, analytics, consultancy, ecommerce, erp, other — or add it to SEGMENTS in your vocabulary file (COMPANY_AI_VOCABULARY, docs/32)
    unknown tier 'strategic'  (1 row: line 9)
      → allowed: A, B, C — or add it to TIERS in your vocabulary file (COMPANY_AI_VOCABULARY, docs/32)
    created is not an ISO date: '12.03.2026'  (1 row: line 14)
    duplicate contact_id 'sc004' (first on line 5)  (1 row: line 62)
deals.csv           280 rows  ok
todos.csv           102 rows  2 problem(s)
    unknown area 'delivery'  (1 row: line 7)
      → allowed: experiments, marketing, operations, rnd, sales — TODO_AREAS is fixed: the code reads these values
    open delivery todo must not have a due_date  (1 row: line 7)

7 distinct problem(s) across 66 row(s); nothing was loaded

# what that means for the person fixing it

distinct problems: 7   rows affected: 66
surfaced in the first pass — unknown tier: True
surfaced in the first pass — not an ISO date: True
surfaced in the first pass — duplicate contact_id: True
