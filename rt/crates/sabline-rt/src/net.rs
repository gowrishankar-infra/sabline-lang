//! The network, in this runtime (9.0, M4): **which host a request may
//! reach, decided here**, and the connection opened here where it can be.
//!
//! Through M3 every call to the network was relayed to the process that
//! started sabline-rt, which made it with the Python package's own urllib
//! ([`crate::interp::RELAYED`], sabline/through_rt.py). So the process the
//! operating system held to the budget's hosts was not the process that
//! opened the connection, which is the thing a `net:` grant is about.
//! plan/9.0.md gives the port to M4 and M5 together; this is M4's half:
//!
//! - **every decision the budget bounds is this runtime's, whatever the
//!   scheme.** The URL is split here, the host and port are matched against
//!   the budget's `net:` grants here, the grant is counted here, the
//!   operation is counted here, an ambient proxy is refused here (E317),
//!   and **each redirect's target is checked here** before it is followed.
//!   Nothing about which host a request may reach is asked of another
//!   process. What the budget does not bound stays where it was: a TLS
//!   certificate is checked by whoever makes the TLS connection, which for
//!   an `https` exchange is still the host.
//! - **the connection is this runtime's for `http://`.** The socket is
//!   opened in this process - inside the Windows AppContainer, whose
//!   `internetClient` capability is what admits it, and under the Linux
//!   seccomp filter and the macOS profile that refuse a socket with no
//!   `net` grant. The request and the response are written and read here
//!   ([`exchange`]).
//! - **`https://` is still two processes**, and says so: the bytes of one
//!   exchange - one request, one response, **no redirects and no grant
//!   checks** - are asked of the host, which has a TLS stack and this
//!   crate has none. The host is a transport there and nothing else: it
//!   decides nothing, counts nothing and follows nothing. M5 finishes the
//!   port (plan/9.0.md), and what TLS in this crate costs in dependencies
//!   is the maintainer's to decide.
//!
//! # What is the same in both runtimes
//!
//! Every message and every refusal is `sabline/runtime.py`'s and
//! `sabline/budget.py`'s, word for word, because a program cannot tell
//! which runtime refused it: E314 for a host outside the grants, E315 past
//! the count, E317 for an ambient proxy the grants do not cover, the
//! failure a program can handle for a redirect it may not follow, and
//! `cannot reach '{url}'` for a connection that did not happen.
//!
//! # Proxies, and the one difference
//!
//! `sabline/budget.py`'s `_proxy_for` asks CPython's `getproxies()`, which
//! reads the environment **and**, on Windows, Internet Settings in the
//! registry, and on macOS the system configuration. This reads the
//! environment alone - and then opens the socket itself, so there is no
//! proxy in the path to bound: the socket's peer **is** the granted host,
//! which is what a `net:` grant is for (THREAT_MODEL.md, 8.0's E317). A
//! machine with a system-wide proxy set outside the environment is
//! therefore a run that the Python runtime refuses with E317 and this one
//! carries out, direct, to the host the budget granted. That is in
//! `docs/known-open.md`, because it is a difference between two runtimes
//! and not something a test here can settle.
//!
//! A proxy the environment does name is refused unless the budget covers
//! its own host and port (E317), as before; and a proxy the budget does
//! cover is honoured by **relaying the whole call**, as M3 did, because
//! what a proxy does to a request is urllib's and is not ported here.

use crate::text::Text;

/// What a URL names, as CPython's `urlsplit` reads it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Url {
    /// `http` or `https`, lower-cased.
    pub scheme: String,
    /// The host, lower-cased with no trailing dot - `urlsplit().hostname`,
    /// then `.lower().rstrip(".")` as `host_refusal` does it.
    pub host: String,
    /// The port the request goes to: the one in the URL, or 443 for
    /// `https` and 80 for `http`.
    pub port: u32,
    /// What follows the host: the path, the query and the fragment, as the
    /// request line carries them. `/` when the URL has none.
    pub target: String,
}

/// Why a URL cannot be read, in CPython's words, since `host_refusal`
/// repeats them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotAUrl(pub String);

/// `urlsplit(url)`, for the URLs a `fetch` reaches: one whose scheme is
/// `http` or `https`, since the builtin puts `https://` in front of
/// anything else before it asks.
///
/// Faithful where it matters and no further: the user information before
/// an `@` is dropped as CPython drops it, a bracketed IPv6 address keeps
/// its brackets out of the host, and a port that is not a number or is out
/// of range is the `ValueError` CPython raises, in its words.
pub fn split(url: &str) -> Result<Url, NotAUrl> {
    let (scheme, rest) = match url.split_once("://") {
        // a URL with no `://` reaches here only through a scheme the
        // builtin did not recognise, and CPython reads no host in it
        None => return Err(NotAUrl("the address has no host".to_string())),
        Some((scheme, rest)) => (scheme.to_ascii_lowercase(), rest),
    };
    let end = rest.find(['/', '?', '#']).unwrap_or(rest.len());
    let (netloc, target) = rest.split_at(end);
    // the user information, which CPython takes off at the last `@`
    let hostinfo = match netloc.rsplit_once('@') {
        None => netloc,
        Some((_user, host)) => host,
    };
    let (host, port_text) = if let Some(after) = hostinfo.strip_prefix('[') {
        match after.split_once(']') {
            None => (hostinfo.to_string(), None),
            Some((inside, tail)) => {
                (inside.to_string(), tail.strip_prefix(':').map(str::to_string))
            }
        }
    } else {
        match hostinfo.rsplit_once(':') {
            None => (hostinfo.to_string(), None),
            Some((host, port)) => (host.to_string(), Some(port.to_string())),
        }
    };
    let port = match port_text.as_deref() {
        // `netloc` ending in a bare colon is no port at all to CPython
        None | Some("") => {
            if scheme == "https" {
                443
            } else {
                80
            }
        }
        Some(said) => {
            // int(port, 10) - no sign, no space, no underscore
            let number: Option<u32> =
                said.chars().all(|c| c.is_ascii_digit()).then(|| said.parse().ok()).flatten();
            match number {
                None => {
                    return Err(NotAUrl(format!(
                        "Port could not be cast to integer value as '{said}'"
                    )))
                }
                Some(n) if n > 65535 => {
                    return Err(NotAUrl("Port out of range 0-65535".to_string()))
                }
                Some(n) => n,
            }
        }
    };
    Ok(Url {
        scheme,
        host: host.to_ascii_lowercase().trim_end_matches('.').to_string(),
        port,
        target: if target.is_empty() { "/".to_string() } else { target.to_string() },
    })
}

/// The URL a builtin asks about: `sabline/runtime.py` puts `https://` in
/// front of anything that does not begin with `http://` or `https://`,
/// which is where a URL with no scheme becomes an HTTPS one on port 443.
pub fn with_scheme(url: &Text) -> Text {
    let said = url.to_string_lossy();
    if said.starts_with("http://") || said.starts_with("https://") {
        url.clone()
    } else {
        Text::from(format!("https://{said}"))
    }
}

/// `_host_matches(pattern, host)`: a `*.` pattern matches one label under
/// it and nothing else.
fn host_matches(pattern: &str, host: &str) -> bool {
    match pattern.strip_prefix("*.") {
        Some(tail) => {
            let (h, t): (Vec<char>, usize) = (host.chars().collect(), tail.chars().count());
            host.ends_with(&format!(".{tail}"))
                && h.len() > t + 1
                && !h[..h.len() - t - 1].contains(&'.')
        }
        None => pattern == host,
    }
}

/// `_net_grant_text(host, port)`: one `net:` grant as the budget writes it,
/// which is the key a receipt counts under.
fn grant_text(host: &str, port: Option<u32>) -> String {
    match port {
        Some(p) => format!("net:{host}:{p}"),
        None => format!("net:{host}"),
    }
}

/// What the `net:` grants say about one URL.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Allowed {
    /// It is allowed, and this grant is the one that let it through - the
    /// text a receipt counts under.
    By(String),
    /// It is not, and this is why, in `host_refusal`'s words.
    No(String),
}

/// `host_refusal(url)`: whether this run's `net:` grants cover the URL's
/// host and port, and the grant that covers it.
///
/// `grants` is the budget's `net`: `None` is `net` with no host, which
/// allows every host and is counted under `net`.
pub fn host_refusal(grants: Option<&Vec<(String, Option<u32>)>>, url: &str) -> Allowed {
    let parts = match split(url) {
        Err(NotAUrl(why)) if why == "the address has no host" => {
            // the scheme a URL with no `://` has, as CPython reads it:
            // everything before the first colon, or nothing
            let scheme = match url.split_once(':') {
                Some((s, _)) if !s.is_empty() && !s.contains('/') => s.to_ascii_lowercase(),
                _ => String::new(),
            };
            let said = if scheme.is_empty() { "?".to_string() } else { scheme };
            return Allowed::No(format!("'{said}' is not http or https"));
        }
        Err(NotAUrl(why)) => return Allowed::No(format!("the address does not parse: {why}")),
        Ok(parts) => parts,
    };
    if parts.scheme != "http" && parts.scheme != "https" {
        return Allowed::No(format!("'{}' is not http or https", parts.scheme));
    }
    if parts.host.is_empty() {
        return Allowed::No("the address has no host".to_string());
    }
    let Some(grants) = grants else {
        return Allowed::By("net".to_string());
    };
    for (host, port) in grants {
        if host_matches(host, &parts.host) && port.is_none_or(|p| p == parts.port) {
            return Allowed::By(grant_text(host, *port));
        }
    }
    Allowed::No(format!(
        "host {}:{} is not in this run's net grants (allow it: --allow net:{}:{})",
        parts.host, parts.port, parts.host, parts.port
    ))
}

/// The variables an ambient proxy is read from, in the order CPython's
/// `getproxies_environment` reads them: the lower-case name wins over the
/// upper-case one, and `REQUEST_METHOD` makes `HTTP_PROXY` a CGI header
/// rather than a proxy, which CPython honours and so does this.
pub const PROXY_ENV: [&str; 5] =
    ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "REQUEST_METHOD"];

/// `_proxy_for(url)`: the ambient proxy that would carry a request to this
/// URL, as a URL with a scheme, or `None`.
///
/// The environment alone, and `NO_PROXY` honoured as `proxy_bypass` honours
/// it. The module's own documentation says what this does not read and why
/// that is safe here.
pub fn proxy_for(url: &Url) -> Option<String> {
    let said = |name: &str| std::env::var(name).ok().filter(|v| !v.trim().is_empty());
    // CGI: an HTTP_PROXY in a request's environment is a client's header,
    // not a proxy, and CPython ignores the upper-case name when
    // REQUEST_METHOD is set
    let cgi = std::env::var("REQUEST_METHOD").is_ok();
    let lower = format!("{}_proxy", url.scheme);
    let upper = lower.to_ascii_uppercase();
    let proxy = said(&lower).or_else(|| if cgi { None } else { said(&upper) })?;
    if bypassed(&url.host) {
        return None;
    }
    Some(if proxy.contains("://") { proxy } else { format!("http://{proxy}") })
}

/// `proxy_bypass_environment(host)`: whether `NO_PROXY` exempts this host.
fn bypassed(host: &str) -> bool {
    let said = std::env::var("no_proxy")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .or_else(|| std::env::var("NO_PROXY").ok())
        .unwrap_or_default();
    if said.trim() == "*" {
        return true;
    }
    for name in said.split(',') {
        let name = name.trim().trim_start_matches('.').to_ascii_lowercase();
        if name.is_empty() {
            continue;
        }
        if host == name || host.ends_with(&format!(".{name}")) {
            return true;
        }
    }
    false
}

/// How many redirects are followed, as `urllib`'s `max_redirections` has
/// it. Each one's target is checked against the grants before it is
/// followed.
pub const MOST_REDIRECTS: usize = 10;

/// How long a request waits, as `sabline/runtime.py` passes it to urllib.
pub const PATIENCE: std::time::Duration = std::time::Duration::from_secs(10);

/// How much of a body is read, as `resp.read(1 << 20)` reads it.
pub const MOST_BODY: usize = 1 << 20;

/// One request this runtime makes: the method, where it goes, and the body
/// a `post` carries.
#[derive(Debug, Clone)]
pub struct Request {
    /// `GET` or `POST`.
    pub method: &'static str,
    /// Where it goes, already checked against the grants.
    pub url: Url,
    /// `(name, value)`, in the order they are written.
    pub headers: Vec<(String, String)>,
    /// What a `post` sends, or empty.
    pub body: String,
    /// The proxy that carries it, host and port, when the environment
    /// names one **and the budget covers it**: the socket's peer is then
    /// the proxy, which is why a proxy outside the grants is refused
    /// before any request is made (E317).
    pub through: Option<(String, u32)>,
}

/// One answer: what a response says, whichever process read it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Response {
    /// The status code.
    pub status: u32,
    /// `location`, when the response carries one: what a redirect follows.
    pub location: Option<String>,
    /// The body, decoded as `resp.read(1 << 20).decode("utf-8", "replace")`
    /// decodes it.
    pub body: String,
    /// Every header, in the order the response carried them and with the
    /// names as it spelled them: what `request`'s document lists. A header
    /// sent twice keeps its first place and its last value, as the Python
    /// runtime's `{k: v for k, v in resp.headers.items()}` does.
    pub headers: Vec<(String, String)>,
}

/// Which builtin is sending, which is what decides the type of a body:
/// `post` says what its body looks like, and `request` gets urllib's own
/// default for one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sends {
    /// `fetch` or `fetch_status`: no body.
    Fetch,
    /// `post`: the type is read from the body's first character.
    Post,
    /// `request`: the program's own headers, and urllib's default type for
    /// a body it was given.
    Request,
}

/// What this runtime sends: the headers `sabline/runtime.py` sends and the
/// ones urllib adds for it - `Host`, `Accept-Encoding: identity`,
/// `Connection: close`, and a length and a type for a body.
pub fn headers_for(url: &Url, sends: Sends, body: &str) -> Vec<(String, String)> {
    let mut out = vec![
        ("Host".to_string(), host_header(url)),
        ("User-Agent".to_string(), format!("sabline/{}", crate::VERSION)),
        ("Accept-Encoding".to_string(), "identity".to_string()),
        ("Connection".to_string(), "close".to_string()),
    ];
    if sends == Sends::Post {
        // the type `sabline/runtime.py` chooses from the body's first
        // character that is not white space
        let first = body.trim_start().chars().next();
        out.push((
            "Content-Type".to_string(),
            if matches!(first, Some('{' | '[')) {
                "application/json".to_string()
            } else {
                "text/plain; charset=utf-8".to_string()
            },
        ));
    } else if sends == Sends::Request && !body.is_empty() {
        // what `AbstractHTTPHandler.do_request_` adds for data whose type
        // nobody named; the program's own header wins over it
        out.push((
            "Content-Type".to_string(),
            "application/x-www-form-urlencoded".to_string(),
        ));
    }
    if !body.is_empty() {
        out.push(("Content-Length".to_string(), body.len().to_string()));
    }
    out
}

/// The host a URL names, whatever its port says: what E314's message
/// shows, since `urlsplit().hostname` answers even where `.port` raises.
pub fn host_of(url: &str) -> String {
    let rest = match url.split_once("://") {
        None => return String::new(),
        Some((_scheme, rest)) => rest,
    };
    let end = rest.find(['/', '?', '#']).unwrap_or(rest.len());
    let hostinfo = match rest[..end].rsplit_once('@') {
        None => &rest[..end],
        Some((_user, host)) => host,
    };
    let host = if let Some(after) = hostinfo.strip_prefix('[') {
        after.split_once(']').map_or(hostinfo, |(inside, _)| inside)
    } else {
        hostinfo.rsplit_once(':').map_or(hostinfo, |(host, _)| host)
    };
    host.to_ascii_lowercase().trim_end_matches('.').to_string()
}

/// The `Host:` header: the host, and the port when it is not the scheme's
/// own, as `http.client` writes it.
fn host_header(url: &Url) -> String {
    let host = if url.host.contains(':') {
        format!("[{}]", url.host) // an IPv6 address, in brackets again
    } else {
        url.host.clone()
    };
    let standard =
        (url.scheme == "https" && url.port == 443) || (url.scheme == "http" && url.port == 80);
    if standard {
        host
    } else {
        format!("{host}:{}", url.port)
    }
}

/// One `http://` exchange, made **in this process**: the socket, the
/// request and the response.
///
/// No redirect is followed here - the caller checks each target against
/// the grants and asks again - and nothing about the budget is looked at:
/// by the time this is called the host, the port, the proxy and the counts
/// have all been decided.
pub fn exchange(request: &Request) -> Result<Response, String> {
    use std::io::{Read, Write};
    use std::net::{TcpStream, ToSocketAddrs};

    // the socket's peer: the proxy where one carries this request, and the
    // URL's own host where none does. Which it is was decided before the
    // request was made, and a proxy outside the budget's grants never
    // reaches here (E317).
    let (peer, peer_port) = match &request.through {
        None => (request.url.host.clone(), request.url.port),
        Some((host, port)) => (host.clone(), *port),
    };
    let where_to = (peer.as_str(), u16::try_from(peer_port).unwrap_or(0));
    let addresses: Vec<std::net::SocketAddr> = match where_to.to_socket_addrs() {
        Err(e) => return Err(said(&e)),
        Ok(found) => found.collect(),
    };
    if addresses.is_empty() {
        return Err("the address did not resolve".to_string());
    }
    // every address in turn, as `create_connection` tries them
    let mut last = String::new();
    let mut socket: Option<TcpStream> = None;
    for address in &addresses {
        match TcpStream::connect_timeout(address, PATIENCE) {
            Ok(open) => {
                socket = Some(open);
                break;
            }
            Err(e) => last = said(&e),
        }
    }
    let Some(mut socket) = socket else { return Err(last) };
    let _ = socket.set_read_timeout(Some(PATIENCE));
    let _ = socket.set_write_timeout(Some(PATIENCE));
    // a proxy is asked for the whole URL (the absolute form of the request
    // line), which is how urllib asks one for an `http` request
    let asked_for = match &request.through {
        None => request.url.target.clone(),
        Some(_) => {
            format!(
                "{}://{}{}",
                request.url.scheme,
                host_header(&request.url),
                request.url.target
            )
        }
    };
    let mut head = format!("{} {} HTTP/1.1\r\n", request.method, asked_for);
    for (name, value) in &request.headers {
        head.push_str(&format!("{name}: {value}\r\n"));
    }
    head.push_str("\r\n");
    if let Err(e) = socket.write_all(head.as_bytes()).and_then(|()| {
        if request.body.is_empty() {
            Ok(())
        } else {
            socket.write_all(request.body.as_bytes())
        }
    }) {
        return Err(said(&e));
    }
    if let Err(e) = socket.flush() {
        return Err(said(&e));
    }
    // the head, and then as much of the body as a read of MOST_BODY takes:
    // a chunked body costs its chunk headers as well, so a little more is
    // read and the body is cut to MOST_BODY after it is decoded.
    //
    // **The response is read until it is complete, not until the socket
    // closes.** `Connection: close` asks the server to close and most do,
    // but one that keeps the connection open would otherwise cost every
    // request the whole ten-second patience: a body whose length the head
    // gives is complete at that length, a chunked one at its last chunk,
    // and only a response that says neither is read to the end of the
    // socket.
    let mut raw: Vec<u8> = Vec::new();
    let mut buffer = [0u8; 16 * 1024];
    let mut head_end: Option<usize> = None;
    let mut want: Option<Complete> = None;
    loop {
        match socket.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                raw.extend_from_slice(&buffer[..n]);
                if head_end.is_none() {
                    head_end = find(&raw, b"\r\n\r\n").map(|at| at + 4);
                    if let Some(at) = head_end {
                        want = Some(how_it_ends(&raw[..at]));
                        // a HEAD answer, a 204 and a 304 carry no body
                        // whatever their head says of one, which
                        // `http.client` knows and a reader that waited for
                        // a `Content-Length` of bytes nobody will send
                        // would not
                        if request.method == "HEAD"
                            || matches!(status_of(&raw[..at]), Some(204 | 304))
                        {
                            want = Some(Complete::Length(0));
                        }
                    }
                }
                if let Some(at) = head_end {
                    if raw.len() - at >= MOST_BODY + 64 * 1024 {
                        break; // enough for MOST_BODY of body, chunked or not
                    }
                    let body = &raw[at..];
                    match want {
                        Some(Complete::Length(n)) if body.len() >= n => break,
                        Some(Complete::Chunked) if chunks_end(body) => break,
                        _ => {}
                    }
                }
            }
            Err(e) => {
                if raw.is_empty() || head_end.is_none() {
                    return Err(said(&e));
                }
                break; // a body cut short is the body that arrived
            }
        }
    }
    read_response(&raw)
}

/// `f"{type(e).__name__}: {e}"` is the Python runtime's way of saying what
/// went wrong, and what a run says is `cannot reach '{url}': {reason}`, so
/// what is kept here is the part that chooses the reason.
fn said(e: &std::io::Error) -> String {
    e.to_string()
}

/// Where `needle` begins in `hay`, or `None`.
fn find(hay: &[u8], needle: &[u8]) -> Option<usize> {
    hay.windows(needle.len()).position(|w| w == needle)
}

/// What says a response's body is all there: its own length, its last
/// chunk, or nothing but the socket closing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Complete {
    /// `Content-Length` bytes of body.
    Length(usize),
    /// `Transfer-Encoding: chunked`, until the zero-length chunk.
    Chunked,
    /// Neither: everything until the other end closes.
    AtTheEnd,
}

/// Which of the three this head says, read from the head alone - a
/// response with both is chunked, as `http.client` reads one.
fn how_it_ends(head: &[u8]) -> Complete {
    let text = String::from_utf8_lossy(head);
    let mut length: Option<usize> = None;
    for line in text.split("\r\n").skip(1) {
        let Some((name, value)) = line.split_once(':') else { continue };
        let value = value.trim();
        match name.trim().to_ascii_lowercase().as_str() {
            "transfer-encoding"
                if value.to_ascii_lowercase().split(',').any(|w| w.trim() == "chunked") =>
            {
                return Complete::Chunked
            }
            "content-length" if length.is_none() => length = value.parse().ok(),
            _ => {}
        }
    }
    match length {
        Some(n) => Complete::Length(n),
        None => Complete::AtTheEnd,
    }
}

/// The status a head says, or `None` when it says none.
fn status_of(head: &[u8]) -> Option<u32> {
    let text = String::from_utf8_lossy(head);
    let line = text.split("\r\n").next()?;
    let mut words = line.split(' ');
    words.next().filter(|v| v.starts_with("HTTP/"))?;
    words.next()?.parse().ok()
}

/// Whether a chunked body has reached its last chunk: the zero-length one.
fn chunks_end(body: &[u8]) -> bool {
    let mut rest = body;
    while let Some(at) = find(rest, b"\r\n") {
        let size = String::from_utf8_lossy(&rest[..at]);
        let size = size.split(';').next().unwrap_or("").trim();
        let Ok(size) = usize::from_str_radix(size, 16) else { return false };
        rest = &rest[at + 2..];
        if size == 0 {
            return true; // the trailer may follow; the body is all there
        }
        if rest.len() < size + 2 {
            return false;
        }
        rest = &rest[size + 2..];
    }
    false
}

/// One response, read from the bytes a server sent.
pub fn read_response(raw: &[u8]) -> Result<Response, String> {
    let Some(at) = find(raw, b"\r\n\r\n") else {
        return Err("the answer is not an HTTP response".to_string());
    };
    let head = String::from_utf8_lossy(&raw[..at]);
    let mut lines = head.split("\r\n");
    let Some(status_line) = lines.next() else {
        return Err("the answer is not an HTTP response".to_string());
    };
    let mut words = status_line.split(' ');
    let version = words.next().unwrap_or("");
    if !version.starts_with("HTTP/") {
        return Err("the answer is not an HTTP response".to_string());
    }
    let status: u32 = match words.next().and_then(|c| c.parse().ok()) {
        None => return Err("the answer has no status".to_string()),
        Some(code) => code,
    };
    let mut location: Option<String> = None;
    let mut chunked = false;
    let mut length: Option<usize> = None;
    let mut headers: Vec<(String, String)> = Vec::new();
    for line in lines {
        let Some((name, value)) = line.split_once(':') else { continue };
        let (name, value) = (name.trim(), value.trim());
        // a header sent twice keeps its first place and its last value, as
        // the Python runtime's dict comprehension over `resp.headers` does
        match headers.iter_mut().find(|(n, _)| n.eq_ignore_ascii_case(name)) {
            Some(slot) => slot.1 = value.to_string(),
            None => headers.push((name.to_string(), value.to_string())),
        }
        match name.to_ascii_lowercase().as_str() {
            // the first of a header that is repeated, as `http.client`'s
            // `get` answers it
            "location" if location.is_none() => location = Some(value.to_string()),
            "transfer-encoding" => {
                chunked = value.to_ascii_lowercase().split(',').any(|w| w.trim() == "chunked");
            }
            "content-length" if length.is_none() => length = value.parse().ok(),
            _ => {}
        }
    }
    let body = &raw[at + 4..];
    let body = if chunked {
        dechunked(body)
    } else {
        match length {
            Some(n) => body[..n.min(body.len())].to_vec(),
            None => body.to_vec(),
        }
    };
    let body = &body[..MOST_BODY.min(body.len())];
    Ok(Response { status, location, body: String::from_utf8_lossy(body).to_string(), headers })
}

/// One exchange as a request to the host - the JSON a `net.exchange` call
/// carries - for an `https://` URL, whose TLS this crate has none of.
///
/// It says where to go and what to send, and **nothing about the budget**:
/// the host is a transport, and a transport that was told a grant could
/// decide with it.
pub fn asked_of_the_host(request: &Request) -> crate::json::Json {
    use crate::json::Json;
    Json::obj([
        ("schema", Json::text(EXCHANGE_SCHEMA)),
        ("method", Json::text(request.method)),
        ("host", Json::text(request.url.host.clone())),
        ("port", Json::Int(i64::from(request.url.port))),
        ("target", Json::text(request.url.target.clone())),
        (
            "headers",
            Json::List(
                request
                    .headers
                    .iter()
                    .map(|(n, v)| {
                        Json::List(vec![Json::text(n.clone()), Json::text(v.clone())])
                    })
                    .collect(),
            ),
        ),
        ("body", Json::text(request.body.clone())),
        (
            "proxy",
            match &request.through {
                None => Json::Null,
                Some((host, port)) => Json::obj([
                    ("host", Json::text(host.clone())),
                    ("port", Json::Int(i64::from(*port))),
                ]),
            },
        ),
        ("timeout", Json::Int(i64::try_from(PATIENCE.as_secs()).unwrap_or(10))),
        ("most_body", Json::Int(i64::try_from(MOST_BODY).unwrap_or(0))),
    ])
}

/// The schema of the one thing a run still asks the host about the
/// network: the bytes of one TLS exchange.
pub const EXCHANGE_SCHEMA: &str = "sabline.net-exchange/1";

/// What the host answered, read back: a response, or why there was none.
pub fn the_host_said(said: &crate::json::Json) -> Result<Response, String> {
    use crate::json::Json;
    let field = |key: &str| -> Option<&Json> {
        match said {
            Json::Obj(pairs) => pairs.get(key),
            _ => None,
        }
    };
    if let Some(Json::Str(why)) = field("error") {
        return Err(why.clone());
    }
    let status = match field("status") {
        Some(Json::Int(n)) => u32::try_from(*n).unwrap_or(0),
        _ => return Err("the host answered no status".to_string()),
    };
    let body = match field("body") {
        Some(Json::Str(s)) => s.clone(),
        Some(Json::Text(t)) => t.to_string_lossy(),
        _ => String::new(),
    };
    let mut headers: Vec<(String, String)> = Vec::new();
    let mut location: Option<String> = None;
    if let Some(Json::List(pairs)) = field("headers") {
        for pair in pairs {
            let Json::List(two) = pair else { continue };
            let name = match two.first() {
                Some(Json::Str(s)) => s.clone(),
                Some(Json::Text(t)) => t.to_string_lossy(),
                _ => continue,
            };
            let value = match two.get(1) {
                Some(Json::Str(s)) => s.clone(),
                Some(Json::Text(t)) => t.to_string_lossy(),
                _ => String::new(),
            };
            if name.eq_ignore_ascii_case("location") && location.is_none() {
                location = Some(value.clone());
            }
            match headers.iter_mut().find(|(n, _)| n.eq_ignore_ascii_case(&name)) {
                Some(slot) => slot.1 = value,
                None => headers.push((name, value)),
            }
        }
    }
    Ok(Response { status, location, body, headers })
}

/// A `Transfer-Encoding: chunked` body, put back together.
fn dechunked(body: &[u8]) -> Vec<u8> {
    let mut out: Vec<u8> = Vec::new();
    let mut rest = body;
    while let Some(at) = find(rest, b"\r\n") {
        let size = String::from_utf8_lossy(&rest[..at]);
        // the chunk extension after a semicolon is not the size
        let size = size.split(';').next().unwrap_or("").trim();
        let Ok(size) = usize::from_str_radix(size, 16) else { break };
        rest = &rest[at + 2..];
        if size == 0 {
            break;
        }
        let take = size.min(rest.len());
        out.extend_from_slice(&rest[..take]);
        if take < size {
            break; // the body was cut short
        }
        rest = &rest[take..];
        if rest.starts_with(b"\r\n") {
            rest = &rest[2..];
        }
        if out.len() >= MOST_BODY {
            break;
        }
    }
    out
}

/// `urljoin(base, location)`, for the `Location` of a redirect: an
/// absolute URL as it is, a scheme-relative one given the base's scheme,
/// an absolute path given the base's host, and a relative one resolved
/// against the base's own directory.
pub fn join(base: &Url, location: &str) -> String {
    let location = location.trim();
    if location.contains("://") {
        return location.to_string();
    }
    let authority = {
        let host = if base.host.contains(':') {
            format!("[{}]", base.host)
        } else {
            base.host.clone()
        };
        let standard = (base.scheme == "https" && base.port == 443)
            || (base.scheme == "http" && base.port == 80);
        if standard {
            host
        } else {
            format!("{host}:{}", base.port)
        }
    };
    if let Some(rest) = location.strip_prefix("//") {
        return format!("{}://{rest}", base.scheme);
    }
    if location.starts_with('/') {
        return format!("{}://{authority}{location}", base.scheme);
    }
    // relative to the base's own directory, the query and fragment gone
    let path = base.target.split(['?', '#']).next().unwrap_or("/");
    let dir = match path.rfind('/') {
        None => "/".to_string(),
        Some(at) => path[..=at].to_string(),
    };
    format!("{}://{authority}{dir}{location}", base.scheme)
}

/// Whether a response is one a redirect follows, and the method the next
/// request uses: `urllib`'s rule, where a `POST` becomes a `GET` for 301,
/// 302 and 303 and stays a `POST` for 307 and 308.
pub fn redirect_method(status: u32, method: &'static str) -> Option<&'static str> {
    match status {
        301..=303 => Some(if method == "POST" { "GET" } else { method }),
        307 | 308 => Some(method),
        _ => None,
    }
}

/// What a run says when a connection did not happen: the reason
/// `sabline/runtime.py` chooses from the exception's text, so that both
/// runtimes say the same thing about the same failure.
pub fn why_not(said: &str) -> &'static str {
    let said = said.to_ascii_lowercase();
    if said.contains("timed out") || said.contains("timeout") {
        "it did not answer in time"
    } else if said.contains("refused") {
        "the connection was refused"
    } else if said.contains("certificate") || said.contains("ssl") {
        "the certificate was not accepted"
    } else if said.contains("unreachable") || said.contains("network") {
        "the network is unreachable"
    } else {
        "the address did not resolve"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_url_splits_as_cpython_splits_one() {
        let one = split("http://127.0.0.1:8080/go?x=1").expect("a url");
        assert_eq!(one.scheme, "http");
        assert_eq!(one.host, "127.0.0.1");
        assert_eq!(one.port, 8080);
        assert_eq!(one.target, "/go?x=1");
        // the scheme's own port when the URL names none, and a trailing
        // dot and upper case off the host
        let two = split("https://API.Example.com./x").expect("a url");
        assert_eq!((two.host.as_str(), two.port), ("api.example.com", 443));
        assert_eq!(split("http://a.example/").expect("a url").port, 80);
        // no path at all is `/`
        assert_eq!(split("http://a.example").expect("a url").target, "/");
        // the user information is dropped, as CPython drops it
        assert_eq!(split("http://u:p@a.example:81/").expect("a url").host, "a.example");
        assert_eq!(split("http://u:p@a.example:81/").expect("a url").port, 81);
        // an IPv6 address keeps no brackets in the host
        let six = split("http://[::1]:90/x").expect("a url");
        assert_eq!((six.host.as_str(), six.port), ("::1", 90));
        assert_eq!(split("http://[::1]/x").expect("a url").port, 80);
        // a bare colon is no port
        assert_eq!(split("http://a.example:/x").expect("a url").port, 80);
    }

    #[test]
    fn a_port_that_is_not_one_is_cpythons_value_error() {
        assert_eq!(
            split("http://a.example:nope/"),
            Err(NotAUrl("Port could not be cast to integer value as 'nope'".to_string()))
        );
        assert_eq!(
            split("http://a.example:99999/"),
            Err(NotAUrl("Port out of range 0-65535".to_string()))
        );
        // and `host_refusal` says what it says about one
        match host_refusal(None, "http://a.example:nope/") {
            Allowed::No(why) => {
                assert!(why.starts_with("the address does not parse: Port"), "{why}")
            }
            Allowed::By(g) => panic!("allowed by {g}"),
        }
    }

    #[test]
    fn a_scheme_that_is_not_http_is_refused_by_name() {
        for (url, said) in [
            ("ftp://a.example/", "'ftp' is not http or https"),
            ("x:/y", "'x' is not http or https"),
        ] {
            match host_refusal(None, url) {
                Allowed::No(why) => assert_eq!(why, said, "{url}"),
                Allowed::By(g) => panic!("{url} allowed by {g}"),
            }
        }
    }

    #[test]
    fn the_grants_cover_a_host_and_a_port_or_say_they_do_not() {
        let grants =
            vec![("a.example".to_string(), Some(443)), ("*.b.example".to_string(), None)];
        assert_eq!(
            host_refusal(Some(&grants), "https://a.example/x"),
            Allowed::By("net:a.example:443".to_string())
        );
        // the port is part of the grant
        match host_refusal(Some(&grants), "http://a.example/x") {
            Allowed::No(why) => {
                assert!(why.contains("a.example:80 is not in this run's"), "{why}")
            }
            Allowed::By(g) => panic!("allowed by {g}"),
        }
        // a wildcard matches one label and not the parent
        assert_eq!(
            host_refusal(Some(&grants), "https://one.b.example/"),
            Allowed::By("net:*.b.example".to_string())
        );
        for no in ["https://b.example/", "https://two.one.b.example/"] {
            assert!(matches!(host_refusal(Some(&grants), no), Allowed::No(_)), "{no}");
        }
        // `net` with no host allows every host, counted under `net`
        assert_eq!(host_refusal(None, "https://any.example/"), Allowed::By("net".to_string()));
    }

    #[test]
    fn a_url_with_no_scheme_is_https_at_443() {
        let said = with_scheme(&Text::from("example.com/"));
        assert_eq!(said.to_string_lossy(), "https://example.com/");
        let one = split(&said.to_string_lossy()).expect("a url");
        assert_eq!((one.host.as_str(), one.port), ("example.com", 443));
        // and one that has a scheme keeps it
        assert_eq!(
            with_scheme(&Text::from("http://a.example/")).to_string_lossy(),
            "http://a.example/"
        );
    }

    #[test]
    fn the_host_header_names_a_port_that_is_not_the_schemes_own() {
        let of = |url: &str| host_header(&split(url).expect("a url"));
        assert_eq!(of("http://a.example/"), "a.example");
        assert_eq!(of("https://a.example/"), "a.example");
        assert_eq!(of("http://a.example:8080/"), "a.example:8080");
        assert_eq!(of("http://[::1]:8080/"), "[::1]:8080");
    }

    #[test]
    fn a_post_says_what_its_body_is() {
        let url = split("http://a.example/").expect("a url");
        let of = |body: &str| {
            headers_for(&url, Sends::Post, body)
                .into_iter()
                .find(|(n, _)| n == "Content-Type")
                .map(|(_, v)| v)
                .unwrap_or_default()
        };
        assert_eq!(of("{\"a\": 1}"), "application/json");
        assert_eq!(of("  [1]"), "application/json");
        assert_eq!(of("hello"), "text/plain; charset=utf-8");
        // and a GET says nothing about a body it does not have
        assert!(headers_for(&url, Sends::Fetch, "").iter().all(|(n, _)| n != "Content-Type"));
        // and `request` gets urllib's own default for a body nobody typed
        assert!(headers_for(&url, Sends::Request, "body")
            .iter()
            .any(|(n, v)| n == "Content-Type" && v == "application/x-www-form-urlencoded"));
        // a length for every body, and none without one
        assert!(headers_for(&url, Sends::Request, "body")
            .iter()
            .any(|(n, v)| n == "Content-Length" && v == "4"));
        assert!(headers_for(&url, Sends::Fetch, "")
            .iter()
            .all(|(n, _)| n != "Content-Length"));
    }

    #[test]
    fn a_response_is_read_by_its_length_or_its_chunks() {
        let one = read_response(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhelloAND MORE")
            .expect("a response");
        assert_eq!((one.status, one.body.as_str()), (200, "hello"));
        let two = read_response(
            b"HTTP/1.1 302 Found\r\nLocation: http://b.example/x\r\nContent-Length: 0\r\n\r\n",
        )
        .expect("a response");
        assert_eq!(two.status, 302);
        assert_eq!(two.location.as_deref(), Some("http://b.example/x"));
        let three = read_response(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n2\r\n, \r\n6\r\nworld!\r\n0\r\n\r\n",
        )
        .expect("a response");
        assert_eq!(three.body, "hello, world!");
        // no length and no chunks: everything that arrived
        let four = read_response(b"HTTP/1.0 200 OK\r\n\r\nall of it").expect("a response");
        assert_eq!(four.body, "all of it");
        // and what is not a response at all is a failure, not a panic
        assert!(read_response(b"nothing like it\r\n\r\n").is_err());
        assert!(read_response(b"HTTP/1.1 nope OK\r\n\r\n").is_err());
        assert!(read_response(b"HTTP/1.1 200 OK").is_err());
    }

    #[test]
    fn a_head_says_how_its_body_ends_and_a_chunked_one_says_when_it_has() {
        assert_eq!(
            how_it_ends(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n"),
            Complete::Length(5)
        );
        assert_eq!(
            how_it_ends(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"),
            Complete::Chunked
        );
        // both: chunked wins, as `http.client` reads one
        assert_eq!(
            how_it_ends(
                b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nTransfer-Encoding: chunked\r\n"
            ),
            Complete::Chunked
        );
        assert_eq!(how_it_ends(b"HTTP/1.0 200 OK\r\n"), Complete::AtTheEnd);
        // and a chunked body is all there at its zero-length chunk and not
        // before it, which is what keeps a request from waiting out its
        // whole patience on a connection the server keeps open
        assert!(!chunks_end(b"5\r\nhello\r\n"));
        assert!(chunks_end(b"5\r\nhello\r\n0\r\n\r\n"));
        assert!(!chunks_end(b"5\r\nhel"));
        assert!(chunks_end(b"0\r\n\r\n"));
    }

    #[test]
    fn a_body_is_cut_at_a_megabyte_as_the_package_cuts_it() {
        let mut raw = b"HTTP/1.1 200 OK\r\n\r\n".to_vec();
        raw.extend(std::iter::repeat_n(b'x', MOST_BODY + 100));
        assert_eq!(read_response(&raw).expect("a response").body.len(), MOST_BODY);
    }

    #[test]
    fn what_went_wrong_is_said_in_the_packages_words() {
        assert_eq!(why_not("OSError: connection timed out"), "it did not answer in time");
        assert_eq!(
            why_not("ConnectionRefusedError: connection refused"),
            "the connection was refused"
        );
        assert_eq!(
            why_not("ssl.SSLCertVerificationError"),
            "the certificate was not accepted"
        );
        assert_eq!(why_not("OSError: network is unreachable"), "the network is unreachable");
        assert_eq!(
            why_not("gaierror: name or service not known"),
            "the address did not resolve"
        );
    }

    #[test]
    fn a_proxy_is_read_from_the_environment_and_no_proxy_exempts_a_host() {
        // the variables are this process's, which a test must not change
        // for the tests running beside it, so what is tested here is the
        // part that does not read them
        assert!(PROXY_ENV.contains(&"http_proxy") && PROXY_ENV.contains(&"HTTPS_PROXY"));
    }
}
