# CVE-2025-6514 (mcp-remote), replayed in Sabline

<!-- description: STOPPED: JFrog's security research team found an OS command injection in `mcp-remote`, an npm package. JFrog's write-up describes it as the proxy that lets ... -->

**mcp-remote, CVE-2025-6514**, 2025-07-09. Also called the mcp-remote RCE. ([The name in use](https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/).) Verdict: **`STOPPED`** - the shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

JFrog's security research team found an OS command injection in
`mcp-remote`, an npm package. JFrog's write-up describes it as the proxy
that lets MCP clients such as Claude Desktop reach a remote MCP server. It is
triggered when the proxy connects to an untrusted MCP server: crafted input
from the server's `authorization_endpoint` response - its OAuth
authorization-server metadata, per JFrog's write-up - reaches an
operating-system command without being sanitised, which lets a malicious
server inject operating-system commands on the machine the proxy is on
(JFrog proves full arbitrary commands on Windows, and executables with
limited parameter control on macOS and Linux). It affects versions 0.0.5
through 0.1.15 and is fixed in 0.1.16; the advisory rates it 9.6. It was
disclosed on 9 July 2025.

## The shape, in Sabline

A field from a server the client does not control reaches a shell. In
Sabline the first half is ordinary - text arrives, from the network or a
file, and is text like any other - and the second half has no builtin. There
is no `exec`, no `shell`, no `system`. The only route from the language to
the operating system is `py`, which needs the `ffi` effect, and a grant that
names modules reaches only the modules it names.

`attack.vel` reads the server's answer - here from a file, so the entry runs
without a network - and hands it to `py("os", "system", ...)`. The run is
given the Python a real MCP proxy would need to parse that answer,
`ffi:json`, and the call is refused with the module named (E311). Nothing
narrower than that grant was needed; the operator did not have to guess that
`os` was the danger, only to say which module the task uses.

## The one line that does the work

--allow io,fs:read:.,ffi:json

`ffi:json` is the line. `ffi` with no module list is every module, and
THREAT_MODEL.md says so; `ffi:json` is a door to one. The reach check (3.3)
holds a call to the module actually reached along the attribute chain, and
refuses rather than allows where it cannot tell which module that is.

### attack.vel

```vel
// The shape of CVE-2025-6514: the untrusted server names its own
// authorization endpoint, and the proxy opens it by handing the string to
// the operating system.
//
// The answer is read from a file here so that this entry runs with no
// network. Where it came from makes no difference to the refusal: a Text
// is a Text, and reaching the operating system is an effect.

fn open_in_browser(url: Text) -> Text uses ffi or fail {
    return try py("os", "system", ["open " + url])
}

fn main() uses io, fs, ffi {
    check read_file("oauth_metadata.json") {
        ok metadata {
            check json_get(metadata, "authorization_endpoint") {
                ok endpoint {
                    print("opening the endpoint the server named")
                    check open_in_browser(endpoint) {
                        ok answer {
                            print("opened")
                        }
                        fail why {
                            print("could not open it: " + why)
                        }
                    }
                }
                fail why {
                    print("no endpoint in the metadata: " + why)
                }
            }
        }
        fail why {
            print("no metadata: " + why)
        }
    }
}
```

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the untrusted server's endpoint reaches the operating system
$ sabline attack.vel --allow io,fs:read:.,ffi:json --receipt receipt.json
opening the endpoint the server named
error[E311] 'py' reaches into Python module 'os', which this run does not allow
  --> attack.vel, line 10
  how to fix (pick one):
    1. allow it: --allow ffi:os,json
    2. or use a program that does not need it
  reference: https://sabline.dev/llms.txt
exit 1

# and with no ffi grant at all
$ sabline attack.vel --allow io,fs:read:.
opening the endpoint the server named
error[E310] 'py' needs the 'ffi' effect, which this run does not allow (it allows: fs:read:.,io)
  --> attack.vel, line 10
  how to fix (pick one):
    1. allow it: sabline <file> --allow fs:read:.,io,ffi
    2. a run with no --allow gets io (5.0); --allow all grants every effect
    3. or use a program that does not need it
  reference: https://sabline.dev/llms.txt
exit 1
```

## Sources

- [OS command injection in mcp-remote when connecting to untrusted MCP servers (JFSA-2025-001290844)](https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/) - JFrog's own research advisory, which found and reported it.
- [CVE-2025-6514: Critical mcp-remote RCE Vulnerability](https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/) - JFrog's own blog write-up (Or Peles, 9 July 2025): what mcp-remote is, the OAuth metadata path, the client (Claude Desktop), and which platforms allow arbitrary commands. The two advisories link it; the four sentences above that the advisories do not carry come from here.
- [GHSA-6xpm-ggf7-wc3p / CVE-2025-6514](https://github.com/advisories/GHSA-6xpm-ggf7-wc3p) - the advisory record: affected versions, severity, and the fixed release.

The entry, its program and its recorded run are in [incidents/mcp-remote-command-injection/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-remote-command-injection/). Every incident, with its verdict, is in [the catalogue](incidents.md).
