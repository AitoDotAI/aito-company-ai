# The Aito requests (table, the where's shape, hits)

  _query companies  where ['company_id'] -> 0 hits
  _query companies  where ['name'] -> 1 hits
  _query contacts   where ['company_id'] -> 2 hits
  _query deals      where ['company_id'] -> 2 hits
  _query touches    where $or of 3 -> 3 hits
  _query todos      where $or of 6 -> 4 hits
  _query documents  where ['company_id'] -> 2 hits

# briefing('Briefing Replica Oy')

company: Briefing Replica Oy [company:briefing-replica-oy]
open deals:
  pilot 24000 EUR [deal:2026-11-02] next: send the pilot scope by 2026-11-04 [touch 2026-11-02T16:05:00] todos: ['Replica: draft the pilot scope']
stakeholders:
  Replica Lead (Commercial lead) last touch 2026-11-02T16:05:00
  Replica Sponsor (CTO) last touch 2026-10-09T12:30:00
touches (newest first):
  2026-11-02T16:05:00 email   reply        Replica Lead: Decision mail sent to the lead.
  2026-10-26T08:10:00 email   reply        Replica Lead: Lead owns the commercial track from now on.
  2026-10-09T12:30:00 meeting conversation Replica Sponsor: Sponsor asked about build versus buy.
notes (by noted_on):
  2026-10-26 Replica: commercial split
  2026-10-09 Replica: kickoff notes
open todos:
  Replica: draft the pilot scope [deal]
  Replica: intro call with the sponsor [stakeholder]
  Replica: post-mortem on the lost deal [deal]

# briefing('Briefing Nodeal Oy'): an account with no deal row

company: Briefing Nodeal Oy [company:briefing-nodeal-oy]
open deals:
stakeholders:
  Nodeal Person (CEO) last touch 2026-10-20T12:15:00
touches (newest first):
  2026-10-20T12:15:00 call    no_answer    Nodeal Person: None
notes (by noted_on):
open todos:

# an unknown company is an error, never an empty briefing

  LookupError: no company with company_id or name 'No Such Company Oy'
