# a consultancy whose work is mostly public sector

classify-account     What kind of company is this, judged only by who works there?
explained-odds       A public-sector account, a champion on board, nothing blocking — what are the odds?
cto-odds             At an account where we know a CTO or Head of IT, how likely is a deal to close?
people-at-customers  Who are the people at accounts that pay us?
accounts-with-cto    Which accounts have a CTO or Head of IT on file?
finance-at-prospects Which people in the IT Manager role work at accounts we are still selling to?
accounting-deals     What is in play across the public-sector industry?
most-dealt-with      Which accounts have we opened the most deals with?

## the technical condition, as sent

{'$or': [{'company_id.$refs.contacts.company_id': {'$exists': {'role': 'CTO'}}}, {'company_id.$refs.contacts.company_id': {'$exists': {'role': 'Head of IT'}}}]}

# an empty instance falls back to the configured vocabulary, not to ours

classify-account     What kind of company is this, judged only by who works there?
explained-odds       A public-sector account, a champion on board, nothing blocking — what are the odds?
cto-odds             At an account where we know a CTO, how likely is a deal to close?
