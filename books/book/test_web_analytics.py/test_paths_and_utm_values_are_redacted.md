# Stored paths and utm values

{"pages": "/unsubscribe/<email>/ /reset/<token>", "utm_campaign": null, "utm_medium": null, "utm_source": null}
{"pages": "/blog/", "utm_campaign": "<invalid>", "utm_medium": "<invalid>", "utm_source": "news_letter"}
leaks: []

# The same, with the redaction stubbed out, must leak

landing_path: email-shaped '/unsubscribe/jane@example.test/'
next_path: long token in '/reset/9f8e7d6c5b4a39281706f5e4d3c2b1a0'
pages: email-shaped '/unsubscribe/jane@example.test/ /reset/9f8e7d6c5b4a39281706f5e4d3c2b1a0'
pages: long token in '/unsubscribe/jane@example.test/ /reset/9f8e7d6c5b4a39281706f5e4d3c2b1a0'
