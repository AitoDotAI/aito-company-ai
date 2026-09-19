# Edit the text and the window, then approve what was actually read

subject: Re: pilot scope (revised)
send_after: 2026-08-19T08:00:00
body: 'Hi Pia,\n\nShorter version: here is the scope.\n'

# Only a staged message is editable

outbox <outbox_id> is approved, not staged — only a staged message is editable

# A field outside the editable set raises, never silently applies

not editable: ['status']
not editable: ['agent']
