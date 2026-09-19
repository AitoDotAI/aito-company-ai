"""Web page fetch for the assistant — the second non-Aito read (docs/16).

Where `web_search` (websearch.py) finds pages, `fetch_page` reads one: give it
a URL and it returns the page's title and readable text, so the model can
summarize a docs page, an article, or a site the operator names. Still a read,
still narration-only — it computes no number; rule 2 keeps every internal
figure in Aito.

It is keyless (a plain HTTP GET), so it needs no provider — but fetching an
arbitrary URL *from the server* is an SSRF surface: the app runs on Azure,
where http://169.254.169.254 is the instance metadata endpoint (managed-
identity tokens). So every URL — and every redirect hop — is guarded to a
**public** http(s) address; loopback, private, link-local, and reserved
ranges are refused, loudly (rule 3), and the refusal is surfaced to the model.

Privacy (docs/06): the URL and the operator's intent reach the target site.
Toggle the tool off with COMPANY_AI_WEB_FETCH=off.
"""

import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from .config import Config

_UA = "company-ai-assistant/1.0 (+https://aito.ai)"
MAX_CHARS = 8000        # readable text handed to the model (keep context tight)
MAX_BYTES = 2_000_000   # cap the download regardless of the page's size
_TEXT_TYPES = {"text/html", "application/xhtml+xml", "text/plain", "text/markdown"}


class FetchError(RuntimeError):
    pass


@dataclass
class Page:
    url: str
    title: str
    text: str
    truncated: bool


def _guard_url(url: str) -> str:
    """Allow only a public http(s) address; return the validated IP to CONNECT to.
    Raises FetchError otherwise — the SSRF guard, applied to the initial URL and
    every redirect hop.

    Returning the IP is what closes the DNS-rebinding TOCTOU: the caller connects
    to this exact validated IP instead of letting `requests` resolve the hostname
    a second time (which an attacker's low-TTL DNS could point at 169.254.169.254
    / loopback between the check and the connect)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise FetchError(f"only http(s) urls are allowed, not {p.scheme or 'none'!r}")
    host = p.hostname
    if not host:
        raise FetchError(f"url has no host: {url!r}")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise FetchError(f"cannot resolve host {host!r}: {exc}")
    chosen = None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise FetchError(
                f"refusing to fetch a non-public address ({ip}) for host {host!r}")
        chosen = chosen or info[4][0]
    if not chosen:
        raise FetchError(f"no address for host {host!r}")
    return chosen


class _HostHeaderSSLAdapter(requests.adapters.HTTPAdapter):
    """Connect to a bare IP (so no second DNS lookup happens) while still doing
    TLS SNI + certificate verification against the real hostname carried in the
    Host header. Used per-request; a fresh session per fetch keeps it isolated."""

    def send(self, request, **kwargs):
        host = request.headers.get("Host")
        if host:
            host = host.split(":")[0]
            self.poolmanager.connection_pool_kw["server_hostname"] = host
            self.poolmanager.connection_pool_kw["assert_hostname"] = host
        try:
            return super().send(request, **kwargs)
        finally:
            self.poolmanager.connection_pool_kw.pop("server_hostname", None)
            self.poolmanager.connection_pool_kw.pop("assert_hostname", None)


def _ip_url(url: str, ip: str) -> str:
    """Rewrite `url`'s host to the validated `ip` (bracketing IPv6), preserving
    scheme/port/path/query — the address we actually connect to."""
    p = urlparse(url)
    host_ip = f"[{ip}]" if ":" in ip else ip
    netloc = f"{host_ip}:{p.port}" if p.port else host_ip
    return p._replace(netloc=netloc).geturl()


class _Reader(HTMLParser):
    """Minimal HTML → text: the <title>, and body text with block tags turned
    into line breaks. Skips script/style/etc. Stdlib only (no bs4 dependency)."""
    _SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    _BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "header",
              "footer", "ul", "ol", "table", "blockquote", "pre",
              "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)
        elif not self._skip:
            self.parts.append(data)


def _extract(html: str) -> tuple[str, str]:
    """(title, readable-text) from an HTML document."""
    reader = _Reader()
    try:
        reader.feed(html)
    except Exception:  # a malformed page still yields whatever parsed
        pass
    title = re.sub(r"\s+", " ", "".join(reader.title)).strip()
    raw = re.sub(r"[ \t]+", " ", "".join(reader.parts))
    lines = [ln.strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln)  # drop blank lines, keep blocks
    return title, text.strip()


@dataclass
class Fetcher:
    timeout: int = 15
    max_chars: int = MAX_CHARS

    def fetch(self, url: str, max_chars: int | None = None) -> Page:
        cap = max_chars or self.max_chars
        resp = None
        # a fresh session per fetch, pinned to the validated IP (no shared state,
        # no DNS re-resolution between guard and connect — closes the SSRF TOCTOU)
        session = requests.Session()
        session.mount("https://", _HostHeaderSSLAdapter())
        for _ in range(5):  # follow redirects manually so each hop is guarded
            ip = _guard_url(url)                     # validates + returns the IP
            parsed = urlparse(url)
            host_header = parsed.netloc               # real host[:port] for routing + SNI
            resp = session.get(
                _ip_url(url, ip),                     # connect to the validated IP literal
                headers={"User-Agent": _UA, "Host": host_header},
                timeout=self.timeout, allow_redirects=False, stream=True)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location")
                resp.close()
                if not loc:
                    raise FetchError(f"redirect with no location from {url!r}")
                url = urljoin(url, loc)
                continue
            break
        else:
            raise FetchError("too many redirects")
        if resp.status_code != 200:
            resp.close()
            raise FetchError(f"fetch {url} -> {resp.status_code}")
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype and ctype not in _TEXT_TYPES:
            resp.close()
            raise FetchError(f"unsupported content-type {ctype!r} (only html/text)")
        raw = b""
        for chunk in resp.iter_content(65536):
            raw += chunk
            if len(raw) >= MAX_BYTES:
                break
        resp.close()
        body = raw.decode(resp.encoding or "utf-8", errors="replace")
        if "html" in ctype or (not ctype and "<html" in body[:2000].lower()):
            title, text = _extract(body)
        else:
            title, text = "", body.strip()
        return Page(url=url, title=title, text=text[:cap].strip(),
                    truncated=len(text) > cap or len(raw) >= MAX_BYTES)


def make_fetcher(config: Config) -> Fetcher | None:
    """The page fetcher, or None when disabled (COMPANY_AI_WEB_FETCH=off)."""
    return Fetcher() if config.fetch_enabled else None
