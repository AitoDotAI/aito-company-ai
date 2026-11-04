
test raised exception PUT /api/v2/schema/contacts -> 400: {"kind": "error", "data": {"code": "schema.create_failed", "message": "Table 'contacts' already exists"}}:
Traceback (most recent call last):
  File "/home/arau/episto/src/aito-company-ai-dev/.venv/lib/python3.12/site-packages/booktest/core/testrun.py", line 105, in run_case
    rv = await maybe_async_call(case, [t], {})
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/arau/episto/src/aito-company-ai-dev/.venv/lib/python3.12/site-packages/booktest/utils/coroutines.py", line 13, in maybe_async_call
    return func(*args2, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^
  File "/home/arau/episto/src/aito-company-ai-dev/book/test_row_writes.py", line 116, in test_concurrent_post_results_all_land
    loaders.create_schema(client)
  File "/home/arau/episto/src/aito-company-ai-dev/src/company_ai/loaders.py", line 293, in create_schema
    client.create_table(name, definition)
  File "/home/arau/episto/src/aito-company-ai-dev/src/company_ai/aito.py", line 168, in create_table
    return self._request("PUT", f"/api/v2/schema/{name}",
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/arau/episto/src/aito-company-ai-dev/src/company_ai/aito.py", line 139, in _request
    raise AitoError(f"{method} {path} -> {response.status_code}: {response.text}")
company_ai.aito.AitoError: PUT /api/v2/schema/contacts -> 400: {"kind": "error", "data": {"code": "schema.create_failed", "message": "Table 'contacts' already exists"}}

