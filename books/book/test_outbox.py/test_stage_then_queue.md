# An agent stages two messages — a threaded reply and a genuine first touch

ob-… status=staged class=re_entry thread=thr-77 reply_to=msg-104
ob-… status=staged class=first_touch thread=None reply_to=None

# The queue the approval view renders — soonest send window first

count=2 counts={'staged': 2}
  2026-08-18T08:00:00  Globex   [re_entry   ] Re: pilot scope
      why: Thread went quiet after the 17.6 meeting; pilot scope was the open item.
  2026-08-19T08:30:00  Initech  [first_touch] Predictive layer for your supplier data
      why: No prior thread; trigger is their new AI announcement.

# Every column the spec names is present on a row

['agent', 'body', 'cc', 'channel', 'class', 'company', 'contact_name', 'created', 'message_id', 'outbox_id', 'rationale', 'reply_to_message_id', 'result', 'send_after', 'sent_at', 'status', 'subject', 'thread_id', 'to', 'updated']
