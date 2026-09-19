# Unknown enum values, empty required fields, and leftover templating (rule 3)

unknown class: unknown class 'newsletter'
unknown channel: unknown channel 'linkedin'
empty rationale: an outbox row needs a rationale
not an address: to 'pia at example dot com' is not an address
unresolved placeholder: body/subject still carry an unresolved {{placeholder}} — the staged text is what goes out verbatim
send_after not a date: send_after is not an ISO date/datetime: 'next tuesday'

# An unknown status filter on the queue raises rather than returning everything

unknown status 'pending'; have ['approved', 'drafted', 'held', 'sent', 'staged', 'struck']
