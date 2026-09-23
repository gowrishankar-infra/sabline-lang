---
slug: mcp-tool-poisoning
title: MCP tool poisoning
date: 2025-04-01
lane: agent
verdict: PARTIAL
budget_line: --max-allow io
verified: false
---

## What happened

On 1 April 2025 Luca Beurer-Kellner and Marc Fischer of Invariant Labs
published a proof of concept in which instructions hidden in an MCP tool's
*description* - text the model reads and the user does not - steer an agent
into doing something the tool does not claim to do. In their demonstration
against Cursor, a poisoned `add` tool made the agent read
`~/.cursor/mcp.json` and `~/.ssh/id_rsa` and pass the contents to the
malicious server in an extra `sidenote` argument: "the agent willingly reads
the user's `~/.cursor/mcp.json` file, and other sensitive files like SSH keys
and sends them to the malicious server." They note that even where the client
asks for confirmation, Cursor "does not show the full tool input" and "the
included SSH key is completely hidden". Reproduction code is published at
`invariantlabs-ai/mcp-injection-experiments`.

## Sources

- [MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks) - the researchers' own write-up, 1 April 2025: the technique, the Cursor demonstration, the files read, and the hidden argument.
- [invariantlabs-ai/mcp-injection-experiments](https://github.com/invariantlabs-ai/mcp-injection-experiments) - the published reproduction code.

## The shape, in Sabline

Two things happen: a model is steered into asking for more than it was
meant to, and a credential leaves in an argument of a call that looks
legitimate. Sabline has an answer to each, and neither is an answer to the
poisoning itself.

First, the ceiling. Sabline's own MCP server holds every run to the
operator's `--max-allow`, which is `io` unless raised. A client that asks it
to run a program with `fs` - however the model was talked into asking - is
refused before anything compiles, and the invocation log records
`"outcome": "ceiling"`. That is the first step here, driven over the
protocol by `ask_for_more.py`.

Second, the argument. `attack.vel` reads the key the sanctioned way, with
`read_file_secret`, and passes it to a host the operator *did* grant, folded
into an otherwise ordinary request. It does not compile: a `Secret of Text`
cannot be an argument to something that performs `net` (E560). The
interesting part is that the network grant was not the thing that refused -
a poisoned tool that exfiltrates to a granted host gets no further than one
that exfiltrates to its own.

## The one line that does the work

    sabline mcp --max-allow io

`--max-allow` is the line: a ceiling no caller can raise, set by the person
who installed the server rather than by the model or the program. `io` is
what it is when nobody sets it (4.0; before 4.0 a caller could ask for more
and get it).

## What this does not cover

Sabline is not an MCP client and does not sit between a model and its
tools: nothing here reads a tool description, judges one, or notices that
one changed. A poisoned description that steers an agent into using its
*other* tools - a shell, an editor, a browser - passes Sabline entirely,
because none of those is a Sabline program.
