# Staging refuses to guess at the thread (the 15.8 defect)

no thread, no claim: no thread_id: resolve the contact's threads first (search, then get_thread — search results truncate). If there genuinely is no prior thread, stage with no_thread=True to say so explicitly.
thread without the message id: thread_id 'thr-77' needs reply_to_message_id (the latest message in that thread) — without it the draft cannot be threaded
message id without a thread: reply_to_message_id without thread_id: resolve the thread first

# An explicit no_thread=True is the only way to start a new conversation

staged with thread_id=None
