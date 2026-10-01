# The GitHub MCP exploit, replayed in Sabline

<!-- description: NOT COVERED: On 26 May 2025 Marco Milanta and Luca Beurer-Kellner of Invariant Labs published an exploit against an agent connected to the official GitHub MCP ... -->

**Private repositories leaked through the GitHub MCP server**, 2025-05-26. Also called toxic agent flows (Invariant Labs' term). ([The name in use](https://news.ycombinator.com/item?id=44097390).) Verdict: **`NOT COVERED`** - nothing in Sabline addresses this shape.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

On 26 May 2025 Marco Milanta and Luca Beurer-Kellner of Invariant Labs
published an exploit against an agent connected to the official GitHub MCP
server. A malicious issue filed on a public repository carried instructions;
when the user asked their agent - Claude Desktop, in the demonstration - to
look at the open issues, the agent followed them, read data out of the
user's private repositories, and published it in a pull request on the
public one. The researchers are explicit that "this is not a flaw in the
GitHub MCP server code itself, but rather a fundamental architectural issue
that must be addressed at the agent system level", and that "GitHub alone
cannot resolve this vulnerability through server-side patches".

## The shape, in Sabline

Everything the agent did, it was allowed to do. It read a public issue, read
private repositories, and opened a pull request; each of those is a call to
one host, with one token, all of it inside any grant that would let the
agent work at all. What went wrong is a relation between two of them -
data from the private side reaching the public side - and a Sabline budget
has no way to express a relation.

A grant names an effect, a host, a port, a path, a Python module, a tool, or
a count. `net:api.github.com:443` is every request to api.github.com.
THREAT_MODEL.md already says a host list "bounds where, not what"; this
incident is that sentence happening. `Secret of T` is the one place Sabline
tracks where a value may go, and it marks the results of `env()` and
`read_file_secret()` only - not what came back from a network call, however
private the repository it came from.

## What this does not cover

Sabline's grants name resources, never flows between them: nothing can say
that data read from one granted place may not be written to another. That
is a stated limit of what an effect budget is, not a defect.

## Sources

- [GitHub MCP Exploited: Accessing private repositories via MCP](https://invariantlabs.ai/blog/mcp-github-vulnerability) - the researchers' own write-up, 26 May 2025: the injection vector, the agent used, what leaked, and where they place responsibility.

The entry, its program and its recorded run are in [incidents/github-mcp-toxic-agent-flow/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/github-mcp-toxic-agent-flow/). Every incident, with its verdict, is in [the catalogue](incidents.md).
