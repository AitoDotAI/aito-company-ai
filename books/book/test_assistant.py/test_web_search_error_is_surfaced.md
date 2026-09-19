# assistant: a web_search backend error is surfaced to the model, not swallowed

trace ok=False error=SearchError: Brave search -> 429: rate limited
error handed back to model: {"error": "SearchError: Brave search -> 429: rate limited"}
