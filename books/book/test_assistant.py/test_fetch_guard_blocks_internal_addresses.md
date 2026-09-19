# fetch_page's SSRF guard: only public http(s) addresses are allowed

  http://169.254.169.254/latest/meta-data/
      -> BLOCK: refusing to fetch a non-public address (169.254.169.254) for host '169.254.169.254'
  http://127.0.0.1:8770/
      -> BLOCK: refusing to fetch a non-public address (127.0.0.1) for host '127.0.0.1'
  http://10.1.2.3/internal
      -> BLOCK: refusing to fetch a non-public address (10.1.2.3) for host '10.1.2.3'
  http://[::1]/
      -> BLOCK: refusing to fetch a non-public address (::1) for host '::1'
  http://0.0.0.0/
      -> BLOCK: refusing to fetch a non-public address (0.0.0.0) for host '0.0.0.0'
  ftp://example.com/x
      -> BLOCK: only http(s) urls are allowed, not 'ftp'
  https://1.1.1.1/
      -> ALLOW
